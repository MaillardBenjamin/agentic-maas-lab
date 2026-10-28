"""Partner MCP tools accept only a short-lived, action-bound bearer grant."""
import os
import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

mcp = FastMCP("maas-simulated-partner-tools", instructions="Services vélo et parking fictifs. Les actions sont fixées par une confirmation métier signée, jamais par le modèle.")


@mcp.tool
async def read_provider_context(question: str) -> dict:
    """Read only the signed supplier's offers, sources, stock and selected order's supplier data."""
    headers = get_http_headers(include={"authorization", "x-maas-provider-read"})
    # Supplier id is a routing hint only; the API verifies the signature and scope.
    import jwt
    scope = jwt.decode(headers.get("x-maas-provider-read", ""), options={"verify_signature": False})
    async with httpx.AsyncClient(timeout=20) as client:
        result = await client.post(os.environ.get("API_URL", "http://api:8000") + "/api/provider-tools/" + scope["provider"] + "/context", json={"question": question}, headers=headers)
        result.raise_for_status()
        return result.json()


async def partner_api(partner, action):
    auth = get_http_headers(include={"authorization"}).get("authorization", "")
    async with httpx.AsyncClient(timeout=15) as client:
        result = await client.request("GET" if action == "availability" else "POST", os.environ.get("API_URL", "http://api:8000") + "/api/partner-tools/" + partner + "/" + action, headers={"Authorization": auth})
        if result.status_code >= 400:
            # Only the business API's controlled explanation, no raw provider/credential error.
            raise ValueError(result.json().get("detail", "Opération partenaire refusée"))
        return result.json()


@mcp.tool
async def bike_availability() -> dict:
    """Inspect fictive bikes and the confirmed action, within the signed operation scope."""
    return await partner_api("bike", "availability")


@mcp.tool
async def bike_apply() -> dict:
    """Execute only the previously confirmed bike action. No model-supplied action or duration."""
    return await partner_api("bike", "apply")


@mcp.tool
async def parking_availability() -> dict:
    """Inspect fictive parking spaces and the confirmed action within the operation scope."""
    return await partner_api("parking", "availability")


@mcp.tool
async def parking_apply() -> dict:
    """Execute only the previously confirmed parking action. Replays have no second effect."""
    return await partner_api("parking", "apply")


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8005, path="/mcp")
