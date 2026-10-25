"""Read-only MCP facade. JWT is forwarded; the API enforces object permissions."""
import os
import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

mcp = FastMCP("maas-ticketing-tools", instructions="Données fictives, lecture seule. Prix et règles versionnés.")


async def api(path, body=None):
    headers = get_http_headers(include={"authorization"})
    auth = headers.get("authorization", "")
    async with httpx.AsyncClient(timeout=10) as client:
        result = await client.request("POST" if body else "GET", os.environ.get("API_URL", "http://api:8000") + "/api" + path, json=body, headers={"Authorization": auth})
        result.raise_for_status()
        return result.json()


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

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8003, path="/mcp")
