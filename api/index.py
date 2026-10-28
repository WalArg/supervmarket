"""API de SuperVmarket (FastAPI) — se despliega como función serverless en Vercel.

Endpoints (todos bajo /api):
    GET  /api/health
    GET  /api/stats
    GET  /api/search?q=...&sort=price_asc|unit_price_asc&only_offers=false
    GET  /api/suggest?q=...
    GET  /api/regions?cp=...
    POST /api/optimize        body: {items:[{ean,qty}], mode, cp, include_clubs, include_shipping}
    POST /api/cart/validate   body: {supermercado, items:[{sku_id,qty}], cp}

Local: cd api && uvicorn index:app --reload --port 8000
"""
import os
import sys
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))
from _lib import db, optimizer, carts, regions, vtex_mcp, benefits, mercadolibre, geocoding, ai  # noqa: E402
from _lib.stores import VTEX_DOMAINS, COMPARE_ONLY        # noqa: E402

STORE_NAMES_LOWER = {s.lower() for s in (*VTEX_DOMAINS.keys(), *COMPARE_ONLY, "thefoodmarket")}

app = FastAPI(title="SuperVmarket API v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class CartItem(BaseModel):
    ean: str
    qty: int = 1
    nombre: str | None = None
    store: str | None = None
    supermercado: str | None = None
    link: str | None = None
    precio: float | None = None
    sku_id: str | None = None


class OptimizeRequest(BaseModel):
    items: list[CartItem]
    mode: Literal["ahorro", "comodidad", "balanceada"] = "ahorro"
    cp: str | None = None
    include_clubs: bool = False
    include_shipping: bool = False
    selected_cards: list[str] = []
    day: str | None = None


class ValidateItem(BaseModel):
    sku_id: str
    qty: int = 1
    nombre: str | None = None


class ValidateRequest(BaseModel):
    supermercado: str
    items: list[ValidateItem]
    cp: str | None = None


class ReceiptRequest(BaseModel):
    image: str
    mime_type: str = "image/jpeg"
    cp: str | None = None


class RecipeRequest(BaseModel):
    prompt: str
    cp: str | None = None


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/stats")
async def stats():
    return vtex_mcp.live_stats_summary()


@app.get("/api/search")
async def search(
    q: str = "",
    sort: str = "price_asc",
    only_offers: bool = False,
    cp: str | None = None,
):
    return await vtex_mcp.search_live_grouped(
        q, sort_by=sort, only_offers=only_offers, cp=cp
    )


@app.get("/api/mcp/search")
async def mcp_live_search(q: str, limit_per_store: int = 18):
    """Endpoint directo del conector MCP VTEX + Coto para diagnóstico e integración."""
    sync_res = await vtex_mcp.live_search_and_sync(q, limit_per_store=limit_per_store, force=True)
    grouped = await db.search_grouped(q, sort_by="price_asc", only_offers=False)
    return {
        "query": q,
        "synced_offers": sync_res.get("synced", 0),
        "stores_hit": sync_res.get("stores", {}),
        "grouped_count": len(grouped),
        "results": grouped[:40],
    }


@app.get("/api/suggest")
async def suggest(q: str):
    return await db.suggest(q)


@app.get("/api/regions")
async def regions_coverage(cp: str):
    """Qué supermercados entregan en ese código postal."""
    return await regions.coverage(cp)


@app.get("/api/geocode/reverse")
async def geocode_reverse(lat: float, lon: float):
    """Geocodificación inversa: GPS (lat/lon) a CP argentino y barrio."""
    return await geocoding.reverse_geocode(lat, lon)


@app.get("/api/geocode/search")
async def geocode_search(q: str = ""):
    """Búsqueda y autocompletado por nombre de barrio, calle o código postal."""
    return await geocoding.search_locations(q)


@app.get("/api/benefits")
async def get_benefits():
    """Catálogo de tarjetas propias, bancos, billeteras y promociones por día de la semana."""
    return benefits.get_benefits_catalog()


@app.get("/api/meli/callback")
async def meli_callback(code: str):
    """Callback de OAuth de Mercado Libre para guardar el token permanente."""
    ok = await mercadolibre.exchange_auth_code(code)
    return {
        "status": "success" if ok else "error",
        "message": "Mercado Libre vinculado exitosamente a SuperVmarket." if ok else "Error al vincular.",
    }


@app.post("/api/optimize")
async def optimize(req: OptimizeRequest):
    items = [i.model_dump() for i in req.items]
    return await optimizer.optimize(
        items,
        mode=req.mode,
        cp=req.cp,
        include_clubs=req.include_clubs,
        include_shipping=req.include_shipping,
        selected_cards=req.selected_cards,
        day=req.day,
    )


@app.post("/api/cart/validate")
async def validate(req: ValidateRequest):
    items = [i.model_dump() for i in req.items]
    return await carts.validate_cart(req.supermercado, items, cp=req.cp)


@app.post("/api/ai/receipt")
async def ai_receipt(req: ReceiptRequest):
    """Vision AI: analiza un ticket de compra y compara precios contra SuperVmarket."""
    return await ai.analyze_receipt(req.image, mime_type=req.mime_type, cp=req.cp)


@app.post("/api/ai/recipe")
async def ai_recipe(req: RecipeRequest):
    """Prompt-to-Cart AI: desglose de receta o menú en changuito optimizado."""
    return await ai.generate_recipe_cart(req.prompt, cp=req.cp)
