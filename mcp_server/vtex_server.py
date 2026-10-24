"""Servidor MCP (Model Context Protocol) oficial para VTEX + Coto Digital en SuperVmarket.

Expone herramientas MCP para:
1. `vtex_search_all_stores`: Búsqueda en vivo en las 12 cadenas (VTEX Catalog System + Coto Endeca),
   unificación por EAN y persistencia instantánea en `supervmarket.db`.
2. `vtex_search_store`: Búsqueda en vivo en una cadena específica.
3. `vtex_check_regions`: Consulta en vivo `/api/checkout/pub/regions` con el Sales Channel (`sc`) real
   de cada cadena para un Código Postal argentino.
4. `vtex_simulate_cart`: Simulación real de carrito `/api/checkout/pub/orderForms/simulation` con
   promociones por volumen (`2x1`, `2do al 70%`), stock real, costo de envío y link de checkout.
"""
import os
import sys
import httpx
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(REPO_ROOT, "api")
SCRAPER_DIR = os.path.join(REPO_ROOT, "scraper")
for p in (REPO_ROOT, API_DIR, SCRAPER_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from _lib.vtex_mcp import (  # noqa: E402
    live_search_and_sync,
    live_lookup_eans,
    fetch_vtex_store_live,
    fetch_coto_live,
)
from _lib.db import search_grouped               # noqa: E402
from _lib.regions import coverage                # noqa: E402
from _lib.carts import validate_cart             # noqa: E402

mcp = FastMCP("vtex-supervmarket")


@mcp.tool()
async def vtex_search_all_stores(
    query: str,
    limit_per_store: int = 16,
    only_offers: bool = False,
) -> dict:
    """Busca un producto en VIVO en los 12 supermercados/farmacias (VTEX + Coto),
    guarda los resultados en la base local y devuelve la comparativa unificada por EAN.
    """
    sync_info = await live_search_and_sync(query, limit_per_store=limit_per_store, force=False)
    grouped = await search_grouped(query, sort_by="price_asc", only_offers=only_offers, limit=80)
    return {
        "query": query,
        "live_synced_offers": sync_info.get("synced", 0),
        "stores_hit": sync_info.get("stores", {}),
        "unified_products_count": len(grouped),
        "products": grouped[:40],
    }


@mcp.tool()
async def vtex_search_store(
    store: str,
    query: str,
    limit: int = 20,
) -> dict:
    """Busca productos en VIVO en una cadena específica (ej: Carrefour, Jumbo, Disco, Vea, Dia, Masonline, Coto, Farmacity)."""
    async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
        if store.lower() == "coto":
            items = await fetch_coto_live(client, query, limit=limit)
        else:
            items = await fetch_vtex_store_live(client, store, query, limit=limit)
    return {
        "store": store,
        "query": query,
        "count": len(items),
        "items": items,
    }


@mcp.tool()
async def vtex_check_regions(postal_code: str = "1414") -> dict:
    """Consulta en vivo `/api/checkout/pub/regions` en todas las cadenas VTEX para un Código Postal."""
    return await coverage(postal_code)


@mcp.tool()
async def vtex_simulate_cart(
    store: str,
    items: list[dict],
    postal_code: str = "1414",
) -> dict:
    """Simula en vivo un carrito VTEX (`/api/checkout/pub/orderForms/simulation`) aplicando 2x1 / 2do al % reales.

    `items` debe ser una lista de dicts con `{"sku_id": "...", "qty": 2, "nombre": "...", "precio": 1000}`.
    """
    return await validate_cart(store, items, cp=postal_code)


@mcp.tool()
async def vtex_lookup_by_eans(eans: list[str]) -> dict:
    """Busca hasta 25 códigos de barras (EAN) exactos en un solo batch por tienda (`fq=alternateIds_Ean:...`)."""
    return await live_lookup_eans(eans)


if __name__ == "__main__":
    mcp.run()
