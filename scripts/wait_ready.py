import asyncio
import os
from temporalio.client import Client

async def main():
    for attempt in range(30):
        try:
            client = await Client.connect(os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"))
            if await client.service_client.check_health():
                print("Temporal gRPC ready")
                return
        except Exception:
            pass
        if attempt < 29:
            await asyncio.sleep(1)
    raise RuntimeError("Temporal non disponible après 30 essais")

asyncio.run(main())
