"""Cobertura por supermercado según el código postal del usuario (VTEX Regions API).

GET /api/checkout/pub/regions?country=ARG&postalCode=XXXX&sc=YY -> [{id: regionId, sellers:[...]}]
Incluye el Sales Channel (`sc`) específico de cada cadena (ej: Jumbo=32, Disco=33, Vea=34)
y cachea en memoria por CP para respuestas instantáneas.
"""
import time
import asyncio
import httpx
from .stores import VTEX_DOMAINS, COMPARE_ONLY, sales_channel

HEADERS = {"Accept": "application/json", "User-Agent": "SuperVmarket/2.0"}
_REGION_CACHE: dict[str, tuple[float, list[dict]]] = {}
CACHE_TTL_SEC = 1800  # 30 minutos


async def _store_coverage(client: httpx.AsyncClient, store: str, domain: str, cp: str) -> dict:
    url = f"{domain}/api/checkout/pub/regions"
    sc = sales_channel(store)
    try:
        r = await client.get(
            url,
            params={"country": "ARG", "postalCode": cp, "sc": sc},
            headers=HEADERS,
        )
        if r.status_code != 200:
            return {"supermercado": store, "delivers": None, "sellers": [], "region_id": None}
        data = r.json()
        if not isinstance(data, list) or not data:
            return {"supermercado": store, "delivers": None, "sellers": [], "region_id": None}
        region_id = data[0].get("id")
        sellers = data[0].get("sellers") or []
        return {
            "supermercado": store,
            "delivers": len(sellers) > 0,
            "sellers": [s.get("id") for s in sellers if s.get("id")],
            "region_id": region_id,
        }
    except Exception:
        return {"supermercado": store, "delivers": None, "sellers": [], "region_id": None}


async def coverage(cp: str) -> list[dict]:
    """Devuelve, por súper, si entrega en ese CP (None = no se pudo determinar)."""
    clean_cp = (cp or "").strip()
    if not clean_cp:
        return []
    now = time.time()
    cached = _REGION_CACHE.get(clean_cp)
    if cached and (now - cached[0]) < CACHE_TTL_SEC:
        return cached[1]

    async with httpx.AsyncClient(timeout=10) as client:
        tasks = [_store_coverage(client, s, d, clean_cp) for s, d in VTEX_DOMAINS.items()]
        results = list(await asyncio.gather(*tasks))

    for store in COMPARE_ONLY:
        results.append({
            "supermercado": store,
            "delivers": None,
            "sellers": [],
            "region_id": None,
            "note": "Cobertura no verificable vía VTEX",
        })

    _REGION_CACHE[clean_cp] = (now, results)
    return results
