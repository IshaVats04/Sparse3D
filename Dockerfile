# Build the web UI
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# API + engine. COLMAP from apt is CPU-only; use a CUDA base image and a CUDA COLMAP build for dense MVS.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends colmap libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY data/samples/ ./data/samples/
COPY --from=frontend /app/frontend/dist ./frontend/dist
ENV SPARSE3D_DATA_DIR=/data
VOLUME /data
EXPOSE 8000
CMD ["python", "src/backend/app.py", "--host", "0.0.0.0", "--port", "8000"]
