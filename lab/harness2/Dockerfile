FROM python:3.12.12-slim
ARG HARNESS2_COMMIT=1cfe254e8d25b15f37048c3730134686abe60335
ADD https://codeload.github.com/google-research/harness2/tar.gz/${HARNESS2_COMMIT} /tmp/harness2.tar.gz
RUN mkdir /opt/harness2 && tar -xzf /tmp/harness2.tar.gz --strip-components=1 -C /opt/harness2 && pip install --no-cache-dir /opt/harness2
COPY lab/harness2/run.py /app/run.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "/app/run.py"]
