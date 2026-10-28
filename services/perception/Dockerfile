FROM python:3.10.19-slim-bookworm@sha256:23f63358922e79a794f71be8f3723c84e5ccca9638af3f74456dc73d6184499e
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 MAX_JOBS=2 CMAKE_BUILD_PARALLEL_LEVEL=2
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg build-essential cmake libopenblas-dev libsndfile1 && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir pip==24.0 setuptools==69.5.1 wheel==0.43.0
COPY services/perception/requirements.txt /opt/perception/requirements.txt
RUN python -m pip install --no-cache-dir -r /opt/perception/requirements.txt
RUN git clone https://github.com/roudimit/whisper-flamingo.git /opt/whisper-flamingo && git -C /opt/whisper-flamingo checkout a0e7e47f9ab6e3f076ca3473812ce8c70003e1f1 \
 && git clone --branch muavic https://github.com/facebookresearch/av_hubert.git /opt/av_hubert && git -C /opt/av_hubert checkout e8a6d4202c208f1ec10f5d41a66a61f96d1c442f \
 && git -C /opt/av_hubert submodule update --init --depth 1
RUN python -m pip install --no-cache-dir --no-build-isolation --no-deps /opt/av_hubert/fairseq
RUN python -m pip install --no-cache-dir editdistance==0.8.1
COPY services/perception/patch_upstream.py /opt/perception/patch_upstream.py
RUN python /opt/perception/patch_upstream.py
COPY services/perception /app
WORKDIR /app
ENV PYTHONPATH=/app:/opt/whisper-flamingo MODEL_DIR=/models
RUN python -c 'import torch, fairseq, cv2, dlib, whisper; print("AVSR runtime imports OK")'
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8005", "--no-access-log"]
