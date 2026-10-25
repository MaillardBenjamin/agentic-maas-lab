FROM python:3.12.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/agents/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY services/agents/ /app/
COPY services/api/maas/ai.py /app/ai_policy.py
COPY services/api/maas/partner_grants.py /app/partner_grants.py
COPY scripts/protocol_smoke.py /app/protocol_smoke.py
CMD ["python", "main.py"]
