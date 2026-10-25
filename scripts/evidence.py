import json
import httpx
from smoke import call, login

demo = login("demo")
print(json.dumps({"integrations": call("/api/integrations", demo), "orders": len(call("/api/orders", demo)), "proofs": [{"digest": p["digest"], "status": p["status"], "chain": p.get("chain")} for p in call("/api/proofs", demo)], "otel_services": httpx.get("http://jaeger:16686/api/services").json()["data"]}, ensure_ascii=False, indent=2))
