import os
import tempfile
import logging
from pathlib import Path

import torch
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from fastapi.responses import Response
from trellis2.pipelines import Trellis2ImageTo3DPipeline
import o_voxel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("haven3d-worker")

API_KEY = os.getenv("WORKER_API_KEY", "")
HOST = os.getenv("WORKER_HOST", "0.0.0.0")
PORT = int(os.getenv("WORKER_PORT", "8000"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "12"))

if not torch.cuda.is_available():
    raise RuntimeError("TRELLIS.2 worker requires a supported NVIDIA CUDA GPU.")

app = FastAPI(title="HAVEN 3D AI Worker")
pipeline = None

@app.on_event("startup")
def load_model():
    global pipeline
    log.info("Loading microsoft/TRELLIS.2-4B. First load downloads model weights.")
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
    pipeline.cuda()
    log.info("TRELLIS.2 model is ready.")

@app.get("/health")
def health():
    return {"ok": True, "model_loaded": pipeline is not None, "cuda": torch.cuda.is_available()}

@app.post("/generate")
async def generate(image: UploadFile = File(...), x_api_key: str = Header(default="")):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Please upload an image.")
    raw = await image.read()
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large.")
    if not raw:
        raise HTTPException(status_code=400, detail="Empty image.")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input_image"
        output_path = Path(tmpdir) / "result.glb"
        input_path.write_bytes(raw)
        try:
            pil_image = Image.open(input_path).convert("RGB")
            with torch.inference_mode():
                mesh = pipeline.run(pil_image)[0]
                mesh.simplify(16_777_216)
                glb = o_voxel.postprocess.to_glb(
                    vertices=mesh.vertices,
                    faces=mesh.faces,
                    attr_volume=mesh.attrs,
                    coords=mesh.coords,
                    attr_layout=mesh.layout,
                    voxel_size=mesh.voxel_size,
                    aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                    decimation_target=1_000_000,
                    texture_size=4096,
                    remesh=True,
                    remesh_band=1,
                    remesh_project=0,
                    verbose=False,
                )
                glb.export(str(output_path), extension_webp=True)
            result = output_path.read_bytes()
            if not result:
                raise RuntimeError("Empty GLB output")
            return Response(
                content=result,
                media_type="model/gltf-binary",
                headers={"Content-Disposition": 'attachment; filename="haven3d.glb"'},
            )
        except Exception as exc:
            log.exception("Generation failed")
            raise HTTPException(status_code=500, detail=f"3D generation failed: {type(exc).__name__}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
