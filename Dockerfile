# OceanGuard AI backend — FastAPI + torch/opencv/rasterio/geopandas.
# python:slim + pip wheels avoid needing system GDAL (rasterio/geopandas/fiona
# ship it in their manylinux wheels); only opencv's libGL runtime is missing
# from the base image, so that's added explicitly below.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# CPU-only torch wheel: the default PyPI build bundles CUDA runtime libs and
# balloons the image by well over a gigabyte for no benefit on a CPU host.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Only what backend/app.py actually reads at runtime (see shared/config/settings.py).
# data/raw/sih_satellite (~4.8GB of reference imagery, unused by any router) is
# deliberately left out via .dockerignore.
COPY backend/ backend/
COPY shared/ shared/
COPY models/ models/
COPY data/raw/synthetic/ data/raw/synthetic/
COPY data/evaluation/ data/evaluation/
COPY data/f3_audit/ data/f3_audit/

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
