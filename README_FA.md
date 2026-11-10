# HAVEN 3D AI — ربات تلگرام تبدیل عکس به مدل سه‌بعدی

این پروژه یک ربات تلگرام است که عکس را دریافت می‌کند و با موتور متن‌باز Microsoft TRELLIS.2 به مدل سه‌بعدی GLB تبدیل می‌کند.

## واقعیت مهم درباره رایگان بودن
- کد ربات و مدل متن‌باز هستند؛ این به معنی رایگان بودن GPU و میزبانی دائمی نیست.
- TRELLIS.2 به Linux و کارت NVIDIA با حداقل 24GB VRAM نیاز دارد (طبق مستندات رسمی پروژه).
- لپ‌تاپ Intel HD 5500 برای اجرای موتور سه‌بعدی مناسب نیست.
- برای آنلاین بودن ربات باید بخش `worker` روی یک سرور GPU اجرا شود. اگر محیط GPU رایگان پیدا شود، ممکن است صف، محدودیت زمان یا خاموشی داشته باشد.
- این مخزن هیچ API پولی یا کلید Tripo ندارد و به سرویس Tripo متصل نمی‌شود.

## ساختار
- `bot/` ربات تلگرام؛ عکس را می‌گیرد و به worker می‌فرستد.
- `worker/` سرویس تولید GLB با TRELLIS.2.
- `requirements-bot.txt` وابستگی‌های ربات.
- `worker/requirements.txt` وابستگی‌های تکمیلی worker؛ خود TRELLIS.2 باید طبق دستور رسمی نصب شود.

## مرحله 1 — ساخت ربات تلگرام
1. در تلگرام با BotFather یک ربات بساز.
2. توکن را فقط در متغیر محیطی `TELEGRAM_BOT_TOKEN` قرار بده؛ آن را در GitHub منتشر نکن.
3. فایل `bot/.env.example` را به `.env` تبدیل کن و مقدارها را وارد کن.

## مرحله 2 — راه‌اندازی موتور TRELLIS.2
این مرحله باید روی Linux با NVIDIA GPU حداقل 24GB VRAM انجام شود. طبق راهنمای رسمی:
```bash
git clone -b main https://github.com/microsoft/TRELLIS.2.git --recursive
cd TRELLIS.2
. ./setup.sh --new-env --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm
```
جزئیات و پیش‌نیازهای به‌روز را در README رسمی بخوان:
https://github.com/microsoft/TRELLIS.2

فایل `worker/trellis_worker.py` را در محیطی قرار بده که پکیج‌های TRELLIS.2 در آن نصب شده‌اند.

## مرحله 3 — اجرای Worker
در محیط TRELLIS.2:
```bash
pip install -r worker/requirements.txt
export WORKER_HOST=0.0.0.0
export WORKER_PORT=8000
export WORKER_API_KEY=یک-رمز-طولانی-و-تصادفی
python worker/trellis_worker.py
```
اگر فایل در مسیر دیگری است، مسیر را اصلاح کن. Worker باید پشت HTTPS قرار بگیرد تا ربات از اینترنت به آن وصل شود. پورت خام HTTP را مستقیماً در اینترنت عمومی باز نکن.

## مرحله 4 — اجرای ربات
```bash
pip install -r requirements-bot.txt
cp bot/.env.example bot/.env
# مقدارها را در bot/.env تنظیم کن
python bot/bot.py
```

مقادیر لازم:
- `TELEGRAM_BOT_TOKEN`: توکن ربات
- `WORKER_URL`: آدرس HTTPS مربوط به worker، مانند `https://your-worker.example`
- `WORKER_API_KEY`: همان رمز worker

## استفاده
کاربر `/start` می‌زند، یک عکس می‌فرستد و در صورت آماده بودن worker فایل `.glb` دریافت می‌کند.

## محدودیت حفظ چهره
Image-to-3D از یک عکس، پشت سر و بخش‌های دیده‌نشده را حدس می‌زند و نمی‌تواند هویت یا شباهت چهره را 100٪ تضمین کند. برای نتیجه بهتر، عکس واضح، نور مناسب و نمای روبه‌رو استفاده کن. برای بازسازی دقیق‌تر، چند زاویه از یک شخص مفید است؛ این نسخه فعلاً یک عکس می‌گیرد.

## امنیت و حریم خصوصی
- توکن تلگرام و کلید worker را در GitHub commit نکن.
- عکس‌های دریافتی موقت هستند و پس از پردازش حذف می‌شوند.
- فقط عکس‌هایی را بارگذاری کن که اجازه استفاده از آن‌ها را داری.
