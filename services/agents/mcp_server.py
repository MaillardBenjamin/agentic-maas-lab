"""Read-only MCP facade. JWT is forwarded; the API enforces object permissions."""
import os
import httpx
from urllib.parse import urlencode
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

mcp = FastMCP("maas-ticketing-tools", instructions="Données fictives, lecture seule. Prix et règles versionnés.")


async def api(path, body=None):
    headers = get_http_headers(include={"authorization", "x-maas-coordination"})
    auth = headers.get("authorization", "")
    async with httpx.AsyncClient(timeout=10) as client:
        result = await client.request("POST" if body else "GET", os.environ.get("API_URL", "http://api:8000") + "/api" + path, json=body, headers={"Authorization": auth, "X-MaaS-Coordination": headers.get("x-maas-coordination", "")})
        result.raise_for_status()
        return result.json()


@mcp.tool
async def read_abt_account() -> dict:
    """Read transport account rights, monthly invoices and usages of the selected traveler. No debit or subscription."""
    return await api("/assistant/abt")


@mcp.tool
async def read_catalog() -> dict:
    """Read fares per operator, effective version, profile rules and seller commissions."""
    return await api("/catalog")


@mcp.tool
async def search_tariffs(question: str) -> dict:
    """Find tariff and SAV source passages through graph traversal."""
    return await api("/knowledge/search", {"query": question})


@mcp.tool
async def read_order(order_id: str) -> dict:
    """Read an order, scoped by the caller's authenticated identity."""
    return await api("/orders/" + order_id)


@mcp.tool
async def read_statement(order_id: str) -> dict:
    """Read exact prepaid, postpaid and distribution amounts for an accessible order."""
    return await api("/orders/" + order_id + "/statement")


@mcp.tool
async def prepare_quote(products: list[str], travel_date: str) -> dict:
    """Prepare a reviewable deterministic quote for the selected traveler, without purchasing."""
    return await api("/assistant/quotes", {"products": products, "travel_date": travel_date})


@mcp.tool
async def list_purchases(traveler_id: str | None = None, limit: int = 10, offset: int = 0) -> dict:
    """List authorized purchases for the authenticated/selected traveler. Never accepts another traveler's scope."""
    params = {"limit": limit, "offset": offset, **({"traveler_id": traveler_id} if traveler_id else {})}
    return await api("/assistant/purchases?" + urlencode(params))


@mcp.tool
async def read_purchase(order_id: str) -> dict:
    """Read one purchase within the authenticated and selected traveler's scope."""
    return await api("/assistant/purchases/" + order_id)


@mcp.tool
async def verify_purchase_proofs(order_id: str) -> dict:
    """Fresh read-only verification of source data, signatures and on-chain commitments."""
    return await api("/assistant/purchases/" + order_id + "/proofs")

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8003, path="/mcp")
