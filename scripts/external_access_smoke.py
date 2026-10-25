"""Read-only provider checks. Never print credentials or provider error messages."""
import json
import os
import re
import time
import httpx


def safe_code(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_:.\-]{1,100}", value) else None


def run():
    checks = []
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        specs = [
            ("openai", "https://api.openai.com/v1/models/" + os.environ.get("OPENAI_MODEL", "gpt-6-luna"), {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}, {}),
            ("bridge", "https://api.bridgeapi.io/v3/payment/payment-requests", {"Client-Id": os.environ["BRIDGE_CLIENT_ID"], "Client-Secret": os.environ["BRIDGE_CLIENT_SECRET"], "Bridge-Version": "2025-01-15"}, {"limit": 1}),
        ]
        for name, url, headers, params in specs:
            started = time.monotonic()
            try:
                response = client.get(url, headers=headers, params=params)
                item = {"service": name, "http_status": response.status_code, "elapsed_ms": round((time.monotonic() - started) * 1000), "authenticated": response.status_code == 200}
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                if response.status_code >= 400 and isinstance(body, dict):
                    error = body.get("error", body)
                    if isinstance(error, dict):
                        item.update(error_code=safe_code(error.get("code")), error_type=safe_code(error.get("type")))
                if name == "openai" and response.status_code == 200:
                    item["model"] = body.get("id")
                if name == "bridge" and response.status_code == 200:
                    item["returned_count"] = len(body.get("resources", []))
                checks.append(item)
            except httpx.HTTPError as error:
                checks.append({"service": name, "network_error": type(error).__name__})
        try:
            response = client.get("http://host.docker.internal:11434/api/tags", timeout=5)
            checks.append({"service": "ollama_host", "http_status": response.status_code, "models": [{"name": m.get("name"), "size": m.get("size")} for m in response.json().get("models", [])] if response.status_code == 200 else []})
        except (httpx.HTTPError, ValueError) as error:
            checks.append({"service": "ollama_host", "unavailable": type(error).__name__})
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    run()
