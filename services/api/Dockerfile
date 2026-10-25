FROM python:3.12.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
COPY services/api/requirements.txt /app/requirements.txt
COPY services/api/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY services/api/maas /app/maas
COPY services/worker /app/worker
COPY fixtures /app/fixtures
COPY tests /app/tests
COPY scripts /app/scripts
CMD ["uvicorn", "maas.api:app", "--host", "0.0.0.0", "--port", "8000"]
