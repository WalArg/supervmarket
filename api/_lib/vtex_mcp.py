"""Motor 100% en vivo Multi-Plataforma (VTEX + Coto Endeca + Shopify) sin base de datos pre-cargada.

1. **VTEX (11 cadenas):**
   - Etapa 1: `/api/catalog_system/pub/products/search?ft={q}&O=OrderByTopSaleDESC` con cookie
     `vtex_segment` regionalizada según el Código Postal (`cp`), descartando `AvailableQuantity <= 0`.
   - Etapa 2: `/api/catalog_system/pub/products/search?fq=alternateIds_Ean:...` (hasta 25 EANs en
     un solo request por supermercado) para completar todas las cadenas que venden el mismo código de barras.
2. **Coto Digital (Oracle Endeca en vivo):**
   - Consulta `/sitios/cdigi/categoria?Ntt={q}&Ns=product.TOTALDEVENTAS%7C1&format=json` (ordenado
     por más vendidos para maximizar cruce de `product.eanPrincipal` con VTEX).
3. **Shopify (`LaBarraCCU` y tiendas Shopify en vivo):**
   - Consulta `/search/suggest.json?q={q}&resources[type]=product`, filtra estrictamente `available == True`
     (con stock en vivo), calcula descuentos (`compare_at_price_max > price`) y cruza por nombre/marca
     con los EANs descubiertos.
4. **Catálogo Efímero en Memoria (`_LIVE_OFFERS_BY_EAN`):**
   - No requiere base de datos pre-cargada (`supervmarket.db`). Guarda en RAM los productos
     consultados en vivo para que el optimizador de Smart Cart arme los carritos al instante.
"""
import os
import sys
import re
import time
import json
import base64
import asyncio
import unicodedata
import urllib.parse
import httpx

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRAPER_DIR = os.path.join(REPO_ROOT, "scraper")
if SCRAPER_DIR not in sys.path:
    sys.path.insert(0, SCRAPER_DIR)

from vtex import parse_vtex_product  # noqa: E402
from coto import parse_coto_record   # noqa: E402
from utils import extraer_unidad_titulo, normalizar_unidad, sanity_precio_unidad  # noqa: E402
from .stores import VTEX_DOMAINS, VTEX_SALES_CHANNELS, supports_cart              # noqa: E402
from . import regions as regions_mod                                              # noqa: E402

LIVE_VTEX_DOMAINS: dict[str, str] = {
    **VTEX_DOMAINS,
    "TheFoodMarket": "https://www.thefoodmarket.com.ar",
}

SHOPIFY_DOMAINS: dict[str, str] = {
    "LaBarraCCU": "https://labarraccu.com.ar",
}

SUPERMARKET_CHAINS = ("Jumbo", "Disco", "Vea", "Carrefour", "Dia", "Masonline")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Memoria en vivo de la sesión (sin base de datos pre-cargada)
_LIVE_PRODUCTS_MEM: dict[str, dict] = {}          # ean -> {ean, nombre, marca, imagen}
_LIVE_OFFERS_MEM: dict[str, dict[str, dict]] = {} # ean -> {supermercado: offer_dict}
_QUERY_GROUPS_CACHE: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 240.0  # 4 minutos


def _norm_text(s: str) -> str:
    if not s:
        return ""
    s_no_acc = "".join(
        c for c in unicodedata.normalize("NFD", str(s).lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9\s]", " ", s_no_acc)


def build_vtex_segment_cookie(sc: str = "1", region_id: str | None = None) -> str:
    payload = {
        "campaigns": None,
        "channel": str(sc or "1"),
        "priceTables": None,
        "regionId": region_id,
        "utm_campaign": None,
        "utm_source": None,
        "utmi_campaign": None,
        "currencyCode": "ARS",
        "currencySymbol": "$",
        "countryCode": "ARG",
        "cultureInfo": "es-AR",
        "channelPrivacy": "public",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


async def fetch_vtex_store_live(
    client: httpx.AsyncClient,
    store: str,
    query: str,
    limit: int = 18,
    order_by: str = "OrderByTopSaleDESC",
    region_id: str | None = None,
) -> list[dict]:
    domain = LIVE_VTEX_DOMAINS.get(store)
    if not domain:
        return []
    base = domain if domain.startswith("http") else f"https://{domain}"
    sc = str(VTEX_SALES_CHANNELS.get(store, "1"))
    sc_qs = f"&sc={sc}" if sc != "1" else ""

    q_clean = query.strip()
    if q_clean.isdigit() and 8 <= len(q_clean) <= 14:
        url = f"{base}/api/catalog_system/pub/products/search?fq=alternateIds_Ean:{q_clean}{sc_qs}"
    else:
        q_enc = urllib.parse.quote(q_clean)
        end = max(0, min(limit - 1, 49))
        url = (
            f"{base}/api/catalog_system/pub/products/search"
            f"?ft={q_enc}&O={order_by}&_from=0&_to={end}{sc_qs}"
        )

    req_headers = dict(HEADERS)
    if region_id or sc != "1":
        seg = build_vtex_segment_cookie(sc=sc, region_id=region_id)
        req_headers["Cookie"] = f"vtex_segment={seg}"

    try:
        r = await client.get(url, headers=req_headers)
        if r.status_code not in (200, 206):
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
        out = []
        for raw_prod in data:
            parsed = parse_vtex_product(raw_prod, store)
            if parsed and int(parsed.get("stock") or 0) > 0:
                out.append(parsed)
        return out
    except Exception:
        return []


async def fetch_vtex_by_eans_live(
    client: httpx.AsyncClient,
    store: str,
    eans: list[str],
    region_id: str | None = None,
) -> list[dict]:
    domain = LIVE_VTEX_DOMAINS.get(store)
    if not domain or not eans:
        return []
    clean_eans = [str(e).strip() for e in eans if str(e).strip().isdigit()][:25]
    if not clean_eans:
        return []

    base = domain if domain.startswith("http") else f"https://{domain}"
    sc = str(VTEX_SALES_CHANNELS.get(store, "1"))
    sc_qs = f"&sc={sc}" if sc != "1" else ""
    fq_qs = "&".join(f"fq=alternateIds_Ean:{e}" for e in clean_eans)
    url = f"{base}/api/catalog_system/pub/products/search?{fq_qs}&_from=0&_to=49{sc_qs}"

    req_headers = dict(HEADERS)
    if region_id or sc != "1":
        seg = build_vtex_segment_cookie(sc=sc, region_id=region_id)
        req_headers["Cookie"] = f"vtex_segment={seg}"

    try:
        r = await client.get(url, headers=req_headers)
        if r.status_code not in (200, 206):
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
        out = []
        for raw_prod in data:
            parsed = parse_vtex_product(raw_prod, store)
            if parsed and int(parsed.get("stock") or 0) > 0:
                out.append(parsed)
        return out
    except Exception:
        return []


async def fetch_coto_live(
    client: httpx.AsyncClient,
    query: str,
    limit: int = 24,
) -> list[dict]:
    """Consulta en vivo Coto Digital ordenando por Más Vendidos (`Ns=product.TOTALDEVENTAS|1`)."""
    q_enc = urllib.parse.quote(query.strip())
    url = (
        f"https://www.coto.com.ar/sitios/cdigi/categoria"
        f"?Ntt={q_enc}&Ns=product.TOTALDEVENTAS%7C1&format=json&Nrpp={limit}"
    )
    try:
        r = await client.get(url, headers=HEADERS)
        if r.status_code != 200:
            return []
        data = r.json()
        out = []
        for m in data.get("contents", [{}])[0].get("Main", []):
            for c in m.get("contents", []):
                for rec in c.get("records", []):
                    parsed = parse_coto_record(rec)
                    if parsed and int(parsed.get("stock") or 0) > 0:
                        out.append(parsed)
                        if len(out) >= limit:
                            return out
        return out
    except Exception:
        return []


async def fetch_shopify_live(
    client: httpx.AsyncClient,
    store: str,
    query: str,
    limit: int = 12,
) -> list[dict]:
    """Consulta en vivo el buscador predictivo de una tienda Shopify (`available == True`)."""
    base = SHOPIFY_DOMAINS.get(store)
    if not base:
        return []
    q_enc = urllib.parse.quote(query.strip())
    url = f"{base}/search/suggest.json?q={q_enc}&resources[type]=product&resources[limit]={limit}"
    try:
        r = await client.get(url, headers=HEADERS)
        if r.status_code != 200:
            return []
        data = r.json()
        prods = (data.get("resources") or {}).get("results", {}).get("products") or []
        out = []
        for p in prods:
            # Filtrar estrictamente productos con stock en vivo
            if not p.get("available", False):
                continue
            try:
                precio = float(p.get("price") or 0)
            except Exception:
                precio = 0.0
            if precio <= 0:
                continue
            try:
                p_lista = float(p.get("compare_at_price_max") or precio)
            except Exception:
                p_lista = precio
            if p_lista < precio:
                p_lista = precio

            descuento = round((1.0 - precio / p_lista) * 100.0, 1) if p_lista > precio else 0.0
            nombre = str(p.get("title") or "").strip()
            if not nombre:
                continue
            cant, u_tit = extraer_unidad_titulo(nombre)
            p_u, u_norm = normalizar_unidad(precio / cant if cant > 0 else precio, u_tit)
            p_u = sanity_precio_unidad(precio, p_u, u_norm)

            prod_id = str(p.get("id") or "")
            raw_url = str(p.get("url") or "").split("?")[0]
            link = f"{base}{raw_url}" if raw_url.startswith("/") else raw_url

            out.append({
                "ean": f"SHOPIFY-{store}-{prod_id}",
                "nombre": nombre,
                "marca": p.get("vendor") or store,
                "imagen": p.get("image") or p.get("featured_image", {}).get("url"),
                "supermercado": store,
                "precio_venta": round(precio, 2),
                "precio_lista": round(p_lista, 2),
                "descuento": descuento,
                "promo_etiqueta": f"{int(round(descuento))}% OFF" if descuento >= 5 else None,
                "promo_tipo": "DIRECT" if descuento >= 5 else None,
                "promo_min_qty": 1,
                "precio_promo_unit": round(precio, 2),
                "requiere_club": False,
                "precio_por_unidad": p_u,
                "unidad_medida": u_norm,
                "stock": 1,
                "itemId": prod_id,
                "link": link,
            })
        return out
    except Exception:
        return []


def _to_offer_dict(d: dict) -> dict:
    precio = float(d["precio_venta"])
    p_lista = float(d.get("precio_lista") or precio)
    if p_lista > precio * 4.0 or p_lista < precio:
        p_lista = precio
        descuento = 0.0
    else:
        descuento = float(d.get("descuento") or 0.0)
    promo_unit = float(d.get("precio_promo_unit") or precio)
    return {
        "supermercado": d["supermercado"],
        "precio": precio,
        "precio_lista": p_lista,
        "stock": int(d.get("stock") or 0) > 0,
        "link": d.get("link") or "",
        "sku_id": str(d.get("itemId") or ""),
        "unit_price": d.get("precio_por_unidad"),
        "unit_measure": d.get("unidad_medida") or "un",
        "discount": descuento,
        "promo_label": d.get("promo_etiqueta"),
        "promo_type": d.get("promo_tipo"),
        "promo_min_qty": int(d.get("promo_min_qty") or 1),
        "promo_unit_price": promo_unit,
        "requires_club": bool(d.get("requiere_club")),
        "supports_cart": supports_cart(d["supermercado"]),
    }


_INVALID_BRANDS = {
    "", "generico", "genérico", "sin marca", "sin marca.", "s/m", "sin definir", "ninguna", "n/a",
}


def _is_valid_brand(b: str | None) -> bool:
    if not b:
        return False
    return b.strip().lower() not in _INVALID_BRANDS


def _store_in_memory(flat_products: list[dict]) -> list[dict]:
    """Agrupa en memoria por EAN, recalcula precios por unidad (`kg`, `l`, `un`) con promo y guarda en RAM."""
    by_ean: dict[str, dict] = {}
    for d in flat_products:
        if not d.get("ean") or not d.get("precio_venta") or int(d.get("stock") or 0) <= 0:
            continue
        ean = str(d["ean"])
        d_marca = (d.get("marca") or "").strip()
        g = by_ean.setdefault(ean, {
            "ean": ean,
            "nombre": d.get("nombre") or "",
            "marca": d_marca if _is_valid_brand(d_marca) else "Genérico",
            "imagen": d.get("imagen") or "",
            "offers_by_store": {},
        })
        if not g["imagen"] and d.get("imagen"):
            g["imagen"] = d["imagen"]
        if not _is_valid_brand(g["marca"]) and _is_valid_brand(d_marca):
            g["marca"] = d_marca

        offer = _to_offer_dict(d)
        g["offers_by_store"][d["supermercado"]] = offer

        # Persistir en el catálogo en memoria de la sesión para el optimizador Smart Cart
        _LIVE_PRODUCTS_MEM[ean] = {
            "ean": ean,
            "nombre": g["nombre"],
            "marca": g["marca"],
            "imagen": g["imagen"],
        }
        mem_offers = _LIVE_OFFERS_MEM.setdefault(ean, {})
        mem_offers[d["supermercado"]] = {**offer, "ean": ean, "nombre": g["nombre"]}

    groups: list[dict] = []
    for ean, g in by_ean.items():
        cant, u_tit = extraer_unidad_titulo(g["nombre"])
        offers = list(g["offers_by_store"].values())
        for o in offers:
            eff_p = float(o.get("promo_unit_price") or o["precio"])
            if cant > 0:
                p_u, u_norm = normalizar_unidad(eff_p / cant, u_tit)
                o["unit_price"] = sanity_precio_unidad(eff_p, p_u, u_norm)
                o["unit_measure"] = u_norm
        groups.append({
            "ean": ean,
            "nombre": g["nombre"],
            "marca": g["marca"],
            "imagen": g["imagen"],
            "offers": offers,
        })
    return groups


async def live_search_and_sync(
    query: str,
    limit_per_store: int = 16,
    only_offers: bool = False,
    cp: str | None = None,
    force: bool = False,
) -> dict:
    """Ejecuta la búsqueda 100% en vivo en los 3 motores (VTEX + Coto Endeca + Shopify)
    filtrando estrictamente productos con stock (regionalizado por CP si se informa).
    """
    q_norm = " ".join(query.lower().strip().split())
    if not q_norm:
        q_norm = "leche"

    cache_key = f"{q_norm}|{'offers' if only_offers else 'all'}|{cp or ''}"
    now = time.time()
    if not force and cache_key in _QUERY_GROUPS_CACHE:
        ts, cached_groups = _QUERY_GROUPS_CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            return {
                "query": q_norm,
                "synced": sum(len(g["offers"]) for g in cached_groups),
                "cached": True,
                "stores": {},
                "groups": cached_groups,
            }

    # Si el usuario informó su Código Postal, obtenemos los regionId de su zona
    region_map: dict[str, str | None] = {}
    if cp:
        try:
            cov_list = await regions_mod.coverage(cp)
            for item in cov_list:
                if item.get("delivers") is False:
                    region_map[item["supermercado"]] = "__NO_DELIVERY__"
                else:
                    region_map[item["supermercado"]] = item.get("region_id")
        except Exception:
            pass

    order_by = "OrderByBestDiscountDESC" if only_offers else "OrderByTopSaleDESC"

    async with httpx.AsyncClient(timeout=5.5, follow_redirects=True) as client:
        vtex_names = [
            st for st in LIVE_VTEX_DOMAINS.keys()
            if region_map.get(st) != "__NO_DELIVERY__"
        ]
        tasks = [
            fetch_vtex_store_live(
                client,
                st,
                q_norm,
                limit=limit_per_store,
                order_by=order_by,
                region_id=region_map.get(st),
            )
            for st in vtex_names
        ]
        tasks.append(fetch_coto_live(client, q_norm, limit=limit_per_store))
        shopify_names = list(SHOPIFY_DOMAINS.keys())
        for sh_st in shopify_names:
            tasks.append(fetch_shopify_live(client, sh_st, q_norm, limit=10))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_names = vtex_names + ["Coto"] + shopify_names
        flat_products: list[dict] = []
        by_store: dict[str, int] = {}
        store_eans: dict[str, set[str]] = {st: set() for st in all_names}
        ean_priority: list[str] = []

        for st_name, res in zip(all_names, results):
            if isinstance(res, list) and res:
                flat_products.extend(res)
                by_store[st_name] = len(res)
                for p in res:
                    e = str(p.get("ean") or "")
                    if e.isdigit() and 8 <= len(e) <= 14:
                        store_eans[st_name].add(e)
                        if e not in ean_priority:
                            ean_priority.append(e)
            else:
                by_store[st_name] = 0

        # Etapa 2: Completado cruzado por EAN (`fq=alternateIds_Ean:...`) en VTEX
        top_eans = ean_priority[:22]
        if top_eans and not q_norm.isdigit():
            ean_tasks = []
            ean_task_stores = []
            for st in SUPERMARKET_CHAINS:
                if region_map.get(st) == "__NO_DELIVERY__":
                    continue
                missing = [e for e in top_eans if e not in store_eans.get(st, set())]
                if missing:
                    ean_tasks.append(
                        fetch_vtex_by_eans_live(
                            client, st, missing[:20], region_id=region_map.get(st)
                        )
                    )
                    ean_task_stores.append(st)
            if ean_tasks:
                ean_results = await asyncio.gather(*ean_tasks, return_exceptions=True)
                for st_name, extra in zip(ean_task_stores, ean_results):
                    if isinstance(extra, list) and extra:
                        flat_products.extend(extra)
                        by_store[st_name] = by_store.get(st_name, 0) + len(extra)

    groups = _store_in_memory(flat_products)
    _QUERY_GROUPS_CACHE[cache_key] = (now, groups)
    return {
        "query": q_norm,
        "synced": len(flat_products),
        "cached": False,
        "stores": by_store,
        "groups": groups,
    }


async def search_live_grouped(
    query: str,
    sort_by: str = "price_asc",
    only_offers: bool = False,
    cp: str | None = None,
) -> list[dict]:
    """Devuelve los grupos de productos 100% desde la búsqueda en vivo (sin base de datos)."""
    q_clean = query.strip()
    effective_q = q_clean if len(q_clean) >= 2 else "coca cola leche"
    res = await live_search_and_sync(
        effective_q, limit_per_store=18, only_offers=only_offers, cp=cp
    )
    groups = [
        {
            **g,
            "offers": list(g["offers"]),
        }
        for g in res.get("groups", [])
    ]

    if only_offers:
        groups = [
            g for g in groups
            if any(o.get("promo_label") or (o.get("discount") or 0) >= 5 for o in g["offers"])
        ]

    first_tok = _norm_text(q_clean).split()[0] if q_clean else ""

    for g in groups:
        if sort_by == "unit_price_asc":
            g["offers"].sort(key=lambda o: (o["unit_price"] is None, o["unit_price"] or 0))
        else:
            g["offers"].sort(key=lambda o: o.get("promo_unit_price") or o["precio"])

    def _group_sort_key(g: dict):
        name_norm = _norm_text(g["nombre"])
        if first_tok:
            starts = 2 if name_norm.startswith(first_tok) else (1 if f" {first_tok}" in name_norm else 0)
        else:
            starts = 1
        stores_cnt = len(g["offers"])
        best_p = min((o.get("promo_unit_price") or o["precio"]) for o in g["offers"]) if g["offers"] else 999999
        return (-starts, -stores_cnt, best_p)

    groups.sort(key=_group_sort_key)
    return groups


async def live_offers_for_eans(eans: list[str], cp: str | None = None):
    """Obtiene en vivo las ofertas para los EANs de Mi Lista (Smart Cart), completando desde VTEX si falta alguno."""
    if not eans:
        return {}, {}

    missing_eans = [e for e in eans if e not in _LIVE_OFFERS_MEM and e.isdigit()]
    if missing_eans:
        await live_lookup_eans(missing_eans, cp=cp)

    out: dict[str, list[dict]] = {}
    names: dict[str, str] = {}
    for ean in eans:
        prod_info = _LIVE_PRODUCTS_MEM.get(ean)
        if prod_info:
            names[ean] = prod_info["nombre"]
        store_map = _LIVE_OFFERS_MEM.get(ean) or {}
        if store_map:
            out[ean] = list(store_map.values())
            if ean not in names and out[ean]:
                names[ean] = out[ean][0].get("nombre") or ean
    return out, names


async def live_lookup_eans(eans: list[str], cp: str | None = None) -> dict:
    clean_eans = [str(e).strip() for e in eans if str(e).strip().isdigit()][:25]
    if not clean_eans:
        return {"eans": [], "synced": 0, "stores": {}}

    async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
        vtex_names = list(LIVE_VTEX_DOMAINS.keys())
        tasks = [fetch_vtex_by_eans_live(client, st, clean_eans) for st in vtex_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    flat: list[dict] = []
    by_store: dict[str, int] = {}
    for st, res in zip(vtex_names, results):
        if isinstance(res, list) and res:
            flat.extend(res)
            by_store[st] = len(res)
        else:
            by_store[st] = 0

    groups = _store_in_memory(flat)
    return {"eans": clean_eans, "synced": len(flat), "stores": by_store, "groups": groups}


def live_stats_summary() -> dict:
    """Estadísticas en vivo de las cadenas conectadas y productos en sesión."""
    store_counts: dict[str, int] = {
        st: 0 for st in (*LIVE_VTEX_DOMAINS.keys(), "Coto", *SHOPIFY_DOMAINS.keys())
    }
    total_offers = 0
    total_promos = 0
    for ean, st_map in _LIVE_OFFERS_MEM.items():
        for st, off in st_map.items():
            store_counts[st] = store_counts.get(st, 0) + 1
            total_offers += 1
            if off.get("promo_label") or (off.get("discount") or 0) >= 5:
                total_promos += 1

    tiendas = [
        {"supermercado": st, "productos": cnt}
        for st, cnt in sorted(store_counts.items(), key=lambda x: (-x[1], x[0]))
    ]
    return {
        "productos": len(_LIVE_PRODUCTS_MEM),
        "ofertas_totales": total_offers,
        "promociones_activas": total_promos,
        "tiendas": tiendas,
    }
