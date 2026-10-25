import time
import httpx

for _ in range(20):
    traces = httpx.get("http://jaeger:16686/api/traces", params={"service": "maas-worker", "limit": 20}, timeout=10).json()["data"]
    connected = [t for t in traces if {"maas-api", "maas-worker"}.issubset({p["serviceName"] for p in t["processes"].values()})]
    if connected:
        break
    time.sleep(0.5)
assert connected, "No connected API/Temporal Worker trace found"
banned = {"gen_ai.prompt", "gen_ai.completion", "http.request.body", "http.request.header.authorization"}
assert not any(tag["key"] in banned for t in connected for span in t["spans"] for tag in span.get("tags", []))
print({"status": "passed", "connected_traces": len(connected), "services": ["maas-api", "maas-worker"], "trace_id": connected[0]["traceID"], "banned_sensitive_attributes": "absent"})
