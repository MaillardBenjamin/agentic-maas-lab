"""Actual MCP and Agno A2A round trips. Fixture model is explicitly NOT an LLM."""
import asyncio
import os
import uuid
import httpx
from fastmcp import Client


async def run():
    async with httpx.AsyncClient(timeout=60) as h:
        response = await h.post("http://api:8000/api/demo/login/lea")
        token = response.json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        cards = []
        for aid in ("conversation", "tariffs", "sav", "clearing", "mobility"):
            r = await h.get("http://agents:8002/a2a/agents/" + aid + "/.well-known/agent-card.json", headers=headers)
            r.raise_for_status()
            assert r.json()["skills"][0]["id"] == aid
            cards.append(aid)
        for aid in ("transport", "bike", "parking"):
            r = await h.get("http://partners:8002/a2a/agents/" + aid + "/.well-known/agent-card.json", headers=headers)
            r.raise_for_status()
            assert r.json()["skills"][0]["id"] == aid
            cards.append(aid)
        rid = str(uuid.uuid4())
        body = {"jsonrpc": "2.0", "id": rid, "method": "message/send", "params": {"message": {"messageId": rid, "role": "user", "parts": [{"kind": "text", "text": "Test protocolaire, sans modèle cloud"}]}}}
        # A separate isolated instance has a deterministic model double; production runtime stays disabled.
        r = await h.post("http://agent-fixture:8002/a2a/agents/conversation/v1/message:send", headers=headers, json=body, timeout=30)
        r.raise_for_status()
        value = r.json()
        assert value["result"]["status"]["state"] == "completed", value
        assert "SIMULATION DE MODÈLE" in str(value)
        assert "2026-demo-v1" in str(value), value
        blocked = await h.post("http://agents:8002/a2a/agents/mobility_operations/v1/message:send", headers=headers, json=body)
        assert blocked.status_code == 403
        blocked = await h.post("http://partners:8002/a2a/agents/bike_operations/v1/message:send", headers=headers, json=body)
        assert blocked.status_code == 403
        if os.environ.get("AI_ENABLED", "false") != "true":
            rejected = await h.post("http://agents:8002/a2a/agents/tariffs/v1/message:send", headers=headers, json=body)
            assert rejected.status_code == 503
    async with Client("http://mcp:8003/mcp", auth=token) as c:
        tools = await c.list_tools()
        assert {t.name for t in tools} == {"read_catalog", "search_tariffs", "read_order", "read_statement", "prepare_quote"}
        catalog = await c.call_tool("read_catalog", {})
        assert "2026-demo-v1" in str(catalog)
        sources = await c.call_tool("search_tariffs", {"question": "régularisation"})
        assert "sav-1" in str(sources)
    async with Client("http://partner-mcp:8005/mcp", auth=token) as c:
        tools = await c.list_tools()
        assert {t.name for t in tools} == {"bike_availability", "bike_apply", "parking_availability", "parking_apply", "read_provider_context"}
    print({"status": "passed", "agent_cards": cards, "a2a_round_trip": "Agno + fixture model, no LLM", "mcp_tools": 10})

asyncio.run(run())
