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
from _lib import db, optimizer, carts, regions, vtex_mcp, benefits, mercadolibre, geocoding, ai, deals  # noqa: E402
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


def _normalize_filter_param(val: str | None) -> str | None:
    """Normalize query filter parameter: strip whitespace, lowercase, map 'todos'/'all'/'' to None."""
    if not val:
        return None
    s = val.strip().lower()
    return None if s in ("todos", "all", "") else s


@app.get("/api/search")
async def search(
    q: str = "",
    sort: str = "price_asc",
    only_offers: bool = False,
    cp: str | None = None,
    vertical: str | None = None,
    store_type: str | None = None,
    grocery_only: bool = False,
):
    clean_v = _normalize_filter_param(vertical)
    clean_st = _normalize_filter_param(store_type)

    results = []
    try:
        results = await vtex_mcp.search_live_grouped(
            q,
            sort_by=sort,
            only_offers=only_offers,
            cp=cp,
            vertical=clean_v,
            store_type=clean_st,
            grocery_only=grocery_only,
        )
    except Exception:
        results = []

    # Resilient fallback to DB if live search returns 0 items (e.g. offline testing or transient network failure)
    if not results and q.strip():
        try:
            results = await db.search_grouped(
                q,
                sort_by=sort,
                only_offers=only_offers,
                vertical=clean_v,
                store_type=clean_st,
                grocery_only=grocery_only,
            )
        except Exception:
            results = []
    return results


@app.get("/api/offers")
async def offers(cp: str | None = None, force: bool = False):
    """Ofertas y mayores descuentos del día comparados en vivo:
    - Supermercados: 70%-80%, liquidaciones directas, 50% y canasta básica.
    - Marketplaces: Electro & Tech, Hogar & Taller, y Ofertas Destacadas con cuotas y sellers.
    """
    return await deals.get_live_discount_tiers(cp=cp, force=force)


@app.get("/api/health/audit")
async def health_audit(cp: str | None = None):
    """Auditoría de salud e integridad de ofertas, enlaces, precios e imágenes."""
    if hasattr(deals, "audit_deals_health"):
        return await deals.audit_deals_health(cp=cp)

    data = await deals.get_live_discount_tiers(cp=cp)
    tiers = data.get("tiers", []) if isinstance(data, dict) else []
    bad_patterns = getattr(
        deals,
        "BAD_IMAGE_PATTERNS",
        ["607590", "879659", "843734", "ids/314352", "ids/345227"],
    )
    issues: list[str] = []
    total_products = 0

    for tier in tiers:
        tier_id = tier.get("id", "unknown")
        sponsored = tier.get("meliSponsored") or {}
        sp_prod = sponsored.get("product") or {}
        sp_offer = sponsored.get("offer") or {}
        sp_price = float(sp_offer.get("precio") or 0)
        sp_list = float(sp_offer.get("precio_lista") or sp_price)
        sp_link = str(sp_offer.get("link") or "")
        sp_img = str(sp_prod.get("imagen") or "")

        if sp_price <= 0 or sp_list < sp_price:
            issues.append(f"{tier_id}: meliSponsored invalid price ({sp_price} / {sp_list})")
        if not sp_link.startswith("https://") or (
            "/p/MLA" not in sp_link and "MLA-" not in sp_link
        ):
            issues.append(f"{tier_id}: meliSponsored invalid link ({sp_link})")
        if not sp_img.startswith("https://"):
            issues.append(f"{tier_id}: meliSponsored invalid image ({sp_img})")

        prods = tier.get("products") or []
        total_products += len(prods)
        for p in prods:
            p_name = p.get("nombre", "unknown")
            p_img = str(p.get("imagen") or "")
            if not p_img.startswith("https://") or any(b in p_img for b in bad_patterns):
                issues.append(f"{tier_id}: product '{p_name}' has invalid/blacklisted image")
            for off in p.get("offers") or []:
                o_price = float(off.get("precio") or 0)
                o_list = float(off.get("precio_lista") or o_price)
                o_link = str(off.get("link") or "")
                if o_price <= 0 or o_list < o_price:
                    issues.append(f"{tier_id}: product '{p_name}' invalid offer price ({o_price})")
                if not o_link.startswith("https://"):
                    issues.append(f"{tier_id}: product '{p_name}' invalid offer link ({o_link})")

    return {
        "status": "healthy" if not issues else "degraded",
        "tiers_count": len(tiers),
        "total_products": total_products,
        "issues": issues,
    }


@app.get("/api/mcp/search")
async def mcp_live_search(
    q: str,
    limit_per_store: int = 18,
    vertical: str | None = None,
    store_type: str | None = None,
    grocery_only: bool = False,
):
    """Endpoint directo del conector MCP VTEX + Coto para diagnóstico e integración."""
    clean_v = _normalize_filter_param(vertical)
    clean_st = _normalize_filter_param(store_type)

    sync_res = {}
    try:
        sync_res = await vtex_mcp.live_search_and_sync(
            q,
            limit_per_store=limit_per_store,
            force=True,
            vertical=clean_v,
            store_type=clean_st,
            grocery_only=grocery_only,
        )
    except Exception:
        sync_res = {"synced": 0, "stores": {}}

    grouped = []
    try:
        grouped = await db.search_grouped(
            q,
            sort_by="price_asc",
            only_offers=False,
            vertical=clean_v,
            store_type=clean_st,
            grocery_only=grocery_only,
        )
    except Exception:
        grouped = []

    return {
        "query": q,
        "vertical": clean_v,
        "store_type": clean_st,
        "grocery_only": grocery_only,
        "synced_offers": sync_res.get("synced", 0) if isinstance(sync_res, dict) else 0,
        "stores_hit": sync_res.get("stores", {}) if isinstance(sync_res, dict) else {},
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
