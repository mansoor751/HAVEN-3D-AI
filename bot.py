import os
import tempfile
import logging
from pathlib import Path

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WORKER_URL = os.getenv("WORKER_URL", "").rstrip("/")
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "").strip()
MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "12"))
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("haven3d")

WELCOME = (
    "به HAVEN 3D AI خوش آمدی!\n\n"
    "یک عکس واضح بفرست تا در صورت فعال بودن موتور GPU، آن را به مدل سه‌بعدی GLB تبدیل کنم.\n"
    "نکته: نتیجه از یک عکس بازسازی تقریبی است و حفظ ۱۰۰٪ چهره تضمین نمی‌شود."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "یک عکس به صورت Photo یا فایل تصویر بفرست.\n"
        "فایل خروجی GLB است و در Blender و Godot قابل وارد کردن است."
    )

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not WORKER_URL or not WORKER_API_KEY:
        await message.reply_text(
            "موتور سه‌بعدی هنوز به سرور GPU وصل نشده است. "
            "پس از تنظیم WORKER_URL و WORKER_API_KEY دوباره امتحان کن."
        )
        return

    photo = None
    if message.photo:
        photo = message.photo[-1]
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        photo = message.document

    if photo is None:
        await message.reply_text("لطفاً یک عکس بفرست.")
        return

    size = getattr(photo, "file_size", 0) or 0
    if size > MAX_IMAGE_MB * 1024 * 1024:
        await message.reply_text(f"حجم عکس باید کمتر از {MAX_IMAGE_MB} مگابایت باشد.")
        return

    await message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)
    status = await message.reply_text("عکس دریافت شد. در حال فرستادن به موتور سه‌بعدی…")

    temp_path = None
    try:
        tg_file = await context.bot.get_file(photo.file_id)
        suffix = ".jpg" if message.photo else Path(message.document.file_name or "image.png").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
        await tg_file.download_to_drive(custom_path=temp_path)

        await status.edit_text("در حال ساخت مدل سه‌بعدی؛ این مرحله ممکن است چند دقیقه طول بکشد…")
        timeout = httpx.Timeout(connect=30, read=900, write=60, pool=30)
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(temp_path, "rb") as image_file:
                response = await client.post(
                    f"{WORKER_URL}/generate",
                    headers={"X-API-Key": WORKER_API_KEY},
                    files={"image": ("input_image", image_file, "application/octet-stream")},
                )
            response.raise_for_status()

        content = response.content
        if not content or len(content) < 100:
            raise RuntimeError("Worker خروجی GLB معتبر برنگرداند.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".glb") as out:
            out.write(content)
            glb_path = out.name

        try:
            await message.reply_document(
                document=open(glb_path, "rb"),
                filename="HAVEN_3D_Model.glb",
                caption="مدل سه‌بعدی آماده شد. می‌توانی آن را در Blender یا Godot وارد کنی."
            )
        finally:
            os.unlink(glb_path)
        await status.delete()
    except httpx.HTTPStatusError as exc:
        log.exception("Worker HTTP error")
        detail = exc.response.text[:500]
        await status.edit_text(f"موتور سه‌بعدی خطا داد ({exc.response.status_code}).\n{detail}")
    except Exception:
        log.exception("Image conversion failed")
        await status.edit_text(
            "تبدیل انجام نشد. ممکن است سرور GPU خاموش باشد یا حافظه کافی نداشته باشد. "
            "لطفاً بعداً دوباره تلاش کن."
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

def main():
    if not TOKEN or "PASTE_" in TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN را در bot/.env تنظیم کن.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))
    app.run_polling()

if __name__ == "__main__":
    main()
