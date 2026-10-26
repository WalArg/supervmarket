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
import html
import asyncio
import unicodedata
import urllib.parse
import httpx

from .parsers import (  # noqa: E402
    parse_vtex_product,
    parse_coto_record,
    extraer_unidad_titulo,
    normalizar_unidad,
    sanity_precio_unidad,
)
from .stores import VTEX_DOMAINS, VTEX_SALES_CHANNELS, supports_cart              # noqa: E402
from . import regions as regions_mod                                              # noqa: E402
from .mercadolibre import fetch_mercadolibre_live                                # noqa: E402

LIVE_VTEX_DOMAINS: dict[str, str] = {
    **VTEX_DOMAINS,
    "TheFoodMarket": "https://www.thefoodmarket.com.ar",
}

SHOPIFY_DOMAINS: dict[str, str] = {
    "LaBarraCCU": "https://labarraccu.com.ar",
}

TIENDANUBE_DOMAINS: dict[str, str] = {
    "LaBarata": "https://labarata.ar",
    "TonelPrivado": "https://www.tonelprivado.com",
    "DePastura": "https://tienda.depastura.com.ar",
}

WOOCOMMERCE_DOMAINS: dict[str, str] = {
    "ArcorEnCasa": "https://arcorencasa.com",
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


def _edit_distance(a: str, b: str) -> int:
    """Distancia de Damerau-Levenshtein rápida para corrección ortográfica (ej: 'pecsi' <-> 'pepsi' = 1)."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > 2:
        return 99
    prev = list(range(lb + 1))
    curr = [0] * (lb + 1)
    prev2 = [0] * (lb + 1)
    for i in range(1, la + 1):
        curr[0] = i
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                curr[j] = min(curr[j], prev2[j - 2] + 1)
        prev2, prev, curr = prev, curr, prev2
    return prev[lb]


def _detect_corrected_query(q_norm: str, vtex_products: list[dict]) -> str | None:
    """Si el usuario escribió un error de tipeo (ej. 'pecsi', 'hugies', 'matarazo') y VTEX Intelligent Search
    encontró la marca/producto real ('pepsi', 'huggies', 'matarazzo'), devuelve el query corregido
    para re-consultar Coto Digital en la Etapa 2.
    """
    if not vtex_products or q_norm.isdigit():
        return None
    q_tokens = _norm_text(q_norm).split()
    if not q_tokens:
        return None

    # Contar frecuencia de tokens en los productos que devolvió VTEX Intelligent Search
    vocab_freq: dict[str, int] = {}
    for p in vtex_products:
        for tok in _norm_text(f"{p.get('marca', '')} {p.get('nombre', '')}").split():
            if len(tok) >= 3:
                vocab_freq[tok] = vocab_freq.get(tok, 0) + 1

    corrected_tokens: list[str] = []
    changed = False
    for qt in q_tokens:
        if len(qt) < 4 or vocab_freq.get(qt, 0) >= 2:
            corrected_tokens.append(qt)
            continue
        max_dist = 1 if len(qt) <= 5 else 2
        best_word = qt
        best_score = (99, 0)
        for cand, freq in vocab_freq.items():
            if freq < 2 or abs(len(cand) - len(qt)) > 1:
                continue
            d = _edit_distance(qt, cand)
            if 1 <= d <= max_dist:
                score = (d, -freq)
                if score < best_score:
                    best_score = score
                    best_word = cand
        if best_word != qt:
            changed = True
        corrected_tokens.append(best_word)

    return " ".join(corrected_tokens) if changed else None


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

    req_headers = dict(HEADERS)
    if region_id or sc != "1":
        seg = build_vtex_segment_cookie(sc=sc, region_id=region_id)
        req_headers["Cookie"] = f"vtex_segment={seg}"

    q_clean = query.strip()
    if q_clean.isdigit() and 8 <= len(q_clean) <= 14:
        url = f"{base}/api/catalog_system/pub/products/search?fq=alternateIds_Ean:{q_clean}{sc_qs}"
        try:
            r = await client.get(url, headers=req_headers)
            if r.status_code not in (200, 206):
                return []
            data = r.json()
            if not isinstance(data, list):
                return []
            return [
                p for raw in data
                if (p := parse_vtex_product(raw, store)) and int(p.get("stock") or 0) > 0
            ]
        except Exception:
            return []

    q_enc = urllib.parse.quote(q_clean)
    count = max(1, min(limit, 40))
    is_sort = "discount:desc" if "Discount" in order_by else "orders:desc"

    # 1. Intentar primero VTEX Intelligent Search (`fuzzy=auto` corrige errores como 'pecsi' -> 'pepsi')
    is_url = (
        f"{base}/api/io/_v/api/intelligent-search/product_search/"
        f"?query={q_enc}&count={count}&sort={is_sort}&fuzzy=auto&operator=and"
    )
    try:
        r = await client.get(is_url, headers=req_headers)
        if r.status_code in (200, 206):
            payload = r.json()
            prods = payload.get("products") if isinstance(payload, dict) else None
            if isinstance(prods, list) and prods:
                out = [
                    p for raw in prods
                    if (p := parse_vtex_product(raw, store)) and int(p.get("stock") or 0) > 0
                ]
                if out:
                    return out
    except Exception:
        pass

    # 2. Fallback a VTEX Catalog Search clásico
    end = max(0, min(limit - 1, 49))
    legacy_url = (
        f"{base}/api/catalog_system/pub/products/search"
        f"?ft={q_enc}&O={order_by}&_from=0&_to={end}{sc_qs}"
    )
    try:
        r = await client.get(legacy_url, headers=req_headers)
        if r.status_code not in (200, 206):
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
        return [
            p for raw in data
            if (p := parse_vtex_product(raw, store)) and int(p.get("stock") or 0) > 0
        ]
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
    if query.strip().isdigit() and len(query.strip()) >= 5:
        return []
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


_KNOWN_BEVERAGE_BRANDS = {
    "branca", "gancia", "campari", "chandon", "catena zapata", "rutini", "trumpeter",
    "luigi bosca", "patagonia", "quilmes", "stella artois", "heineken", "corona",
    "brahma", "andes", "smirnoff", "absolut", "tanqueray", "bombay", "beefeater",
    "johnnie walker", "chivas", "jack daniels", "jameson", "vittone", "1882", "sernova",
    "skyy", "buhero negro", "aperol", "jagermeister",
}


async def fetch_tiendanube_live(
    client: httpx.AsyncClient,
    store: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Consulta en vivo el buscador de una tienda Tiendanube pública (extrayendo microdatos Schema.org JSON-LD)."""
    if query.strip().isdigit() and len(query.strip()) >= 5:
        return []
    base = TIENDANUBE_DOMAINS.get(store)
    if not base:
        return []
    q_enc = urllib.parse.quote(query.strip())
    url = f"{base}/search/?q={q_enc}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-419,es;q=0.9",
    }
    q_words = [w for w in _norm_text(query).split() if len(w) >= 2]
    try:
        r = await client.get(url, headers=headers, timeout=4.0, follow_redirects=True)
        if r.status_code != 200:
            return []
        json_lds = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        out = []
        for j in json_lds:
            if len(out) >= limit:
                break
            try:
                data = json.loads(j.strip())
                if data.get("@type") == "Product":
                    name = html.unescape(data.get("name") or "").strip()
                    offers = data.get("offers") or {}
                    price_str = str(offers.get("price") or "0").replace(",", ".")
                    price = float(price_str)
                    link = offers.get("url") or data.get("mainEntityOfPage", {}).get("@id") or ""
                    image = data.get("image") or ""
                    in_stock = "InStock" in str(offers.get("availability") or "")
                    if not name or price <= 0 or not in_stock:
                        continue
                    # Si buscó texto, descartar recomendaciones de Tiendanube que no contengan ninguna palabra buscada
                    if q_words:
                        nom_norm = _norm_text(name)
                        if not any(w in nom_norm for w in q_words):
                            continue
                    cant, u_tit = extraer_unidad_titulo(name)
                    p_u, u_norm = normalizar_unidad(price / cant if cant > 0 else price, u_tit)
                    p_u = sanity_precio_unidad(price, p_u, u_norm)
                    slug = link.rstrip("/").split("/")[-1] if "/" in link else name[:12]
                    cat = (
                        "Bebidas" if store == "TonelPrivado"
                        else ("Carnes" if store == "DePastura" else "Frutas y Verduras")
                    )
                    b_detected = store
                    if store == "TonelPrivado":
                        nom_lower = name.lower()
                        for kb in _KNOWN_BEVERAGE_BRANDS:
                            if kb in nom_lower:
                                b_detected = kb.title()
                                break
                    out.append({
                        "ean": f"TN_{store.upper()}_{slug}",
                        "nombre": name,
                        "marca": b_detected,
                        "modelo": "",
                        "tipo": "",
                        "imagen": image,
                        "supermercado": store,
                        "precio_venta": price,
                        "precio_lista": price,
                        "descuento": 0.0,
                        "promo_etiqueta": None,
                        "promo_tipo": None,
                        "promo_min_qty": 1,
                        "precio_promo_unit": price,
                        "requiere_club": False,
                        "precio_por_unidad": p_u,
                        "unidad_medida": u_norm,
                        "categorias": cat,
                        "stock": 1,
                        "itemId": slug,
                        "link": link,
                    })
            except Exception:
                continue
        return out
    except Exception:
        return []


async def fetch_woocommerce_live(
    client: httpx.AsyncClient,
    store: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Consulta en vivo el catálogo Store API público de tiendas WooCommerce (como Arcor en Casa)."""
    if query.strip().isdigit() and len(query.strip()) >= 5:
        return []
    base = WOOCOMMERCE_DOMAINS.get(store)
    if not base:
        return []
    q_enc = urllib.parse.quote(query.strip())
    url = f"{base}/wp-json/wc/store/v1/products?search={q_enc}&per_page={limit}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    try:
        r = await client.get(url, headers=headers, timeout=4.0)
        if r.status_code != 200:
            return []
        items = r.json()
        out = []
        for p in items:
            if not p.get("is_purchasable") or not p.get("is_in_stock"):
                continue
            prices = p.get("prices") or {}
            raw_p = float(prices.get("price") or 0)
            minor = int(prices.get("currency_minor_unit") or 2)
            precio = round(raw_p / (10 ** minor), 2)
            if precio <= 0:
                continue
            raw_reg = float(prices.get("regular_price") or raw_p)
            p_lista = round(raw_reg / (10 ** minor), 2)
            if p_lista < precio:
                p_lista = precio
            descuento = round((1.0 - precio / p_lista) * 100.0, 1) if p_lista > precio else 0.0
            images = p.get("images") or []
            img = images[0].get("src") if images else ""
            nom = p.get("name") or ""
            cant, u_tit = extraer_unidad_titulo(nom)
            p_u, u_norm = normalizar_unidad(precio / cant if cant > 0 else precio, u_tit)
            p_u = sanity_precio_unidad(precio, p_u, u_norm)
            out.append({
                "ean": f"WC_{store.upper()}_{p['id']}",
                "nombre": nom,
                "marca": "Arcor" if store == "ArcorEnCasa" else store,
                "modelo": "",
                "tipo": "",
                "imagen": img,
                "supermercado": store,
                "precio_venta": precio,
                "precio_lista": p_lista,
                "descuento": descuento,
                "promo_etiqueta": f"{int(round(descuento))}% OFF" if descuento >= 5 else None,
                "promo_tipo": "DIRECT" if descuento >= 5 else None,
                "promo_min_qty": 1,
                "precio_promo_unit": precio,
                "requiere_club": False,
                "precio_por_unidad": p_u,
                "unidad_medida": u_norm,
                "categorias": "Almacén",
                "stock": 1,
                "itemId": str(p["id"]),
                "link": p.get("permalink") or "",
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
        "sku_id": str(d.get("itemId") or d.get("sku") or ""),
        "unit_price": d.get("unit_price") or d.get("precio_por_unidad"),
        "unit_measure": d.get("unit_type") or d.get("unidad_medida") or "un",
        "discount": descuento,
        "promo_label": d.get("promo_label") or d.get("promo_etiqueta"),
        "promo_type": d.get("promo_tipo"),
        "promo_min_qty": int(d.get("promo_min_qty") or 1),
        "promo_unit_price": promo_unit,
        "requires_club": bool(d.get("requires_club") or d.get("requiere_club")),
        "supports_cart": supports_cart(d["supermercado"]),
        "unit_multiplier": float(d.get("unit_multiplier") or 1.0),
        "nombre": d.get("nombre") or "",
        # Metadata enriquecida de Mercado Libre y Marketplace
        "seller_name": d.get("seller_name"),
        "seller_reputation": d.get("seller_reputation"),
        "power_seller_status": d.get("power_seller_status"),
        "free_shipping": bool(d.get("free_shipping")),
        "free_shipping_threshold": d.get("free_shipping_threshold"),
        "shipping_cost": d.get("shipping_cost"),
        "is_full": d.get("is_full"),
        "meli_options": d.get("meli_options"),
    }


_INVALID_BRANDS = {
    "", "generico", "genérico", "sin marca", "sin marca.", "s/m", "sin definir", "ninguna", "n/a",
}

_FILLER_TOKENS = {
    "uat", "uht", "larga", "vida", "brick", "tetra", "brik", "botella", "lata",
    "envase", "paquete", "bolsa", "caja", "sachet", "doypack", "pouch", "pet",
    "clasica", "clasico", "tradicional", "regular", "sabor", "fortificada", "fortificado",
    "suave", "palo", "hoja", "tipo",
    "vitamina", "vitaminas", "calcio", "hierro", "con", "de", "del", "la", "el", "los",
    "las", "para", "en", "por", "al", "y", "o", "x", "un", "u", "uni", "unid", "unidades",
    "gr", "grs", "g", "kg", "kgs", "ml", "cc", "cm3", "l", "lt", "lts", "litro", "litros",
}

_NUMBER_WORDS = {"3": "tres", "9": "nueve", "5": "cinco", "7": "siete", "2": "dos"}
_EAN_ALIASES: dict[str, set[str]] = {}


def _is_valid_brand(b: str | None) -> bool:
    if not b:
        return False
    return b.strip().lower() not in _INVALID_BRANDS


def _norm_brand_key(b: str) -> str:
    tokens = [_NUMBER_WORDS.get(t, t) for t in _norm_text(b).split()]
    return " ".join(tokens)


def _singularize_token(t: str) -> str:
    if len(t) > 5 and t.endswith("es") and t[-3] in "nlrdz":
        return t[:-2]
    if len(t) > 4 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        return t[:-1]
    return t


def _canonical_signature(nombre: str, marca: str):
    """Genera una firma canónica estricta `(brand_key, cant, u_norm, is_multipack, content_tokens)`
    para fusionar únicamente productos idénticos que difieren de EAN entre cadenas.
    """
    if not _is_valid_brand(marca) or not nombre:
        return None
    brand_key = _norm_brand_key(marca)
    if not brand_key:
        return None

    cant, u_tit = extraer_unidad_titulo(nombre)
    if cant <= 0:
        return None
    _, u_norm = normalizar_unidad(1.0, u_tit)

    s = "".join(
        c for c in unicodedata.normalize("NFD", nombre.lower())
        if unicodedata.category(c) != "Mn"
    )
    is_multipack = bool(
        re.search(r"\b\d+\s*x\s*\d+|\bx\s*\d+\s*(?:un|u|uni|unid|unidades|latas?|botellas?)\b|\b(?:multipack|pack|sixpack)\b", s)
    )

    # Normalizar sinónimos exactos de la industria alimentaria argentina
    s = re.sub(r"\b0\s*%?\s*tenor\s+graso\b|\b0\s*%\s*grasa\b", " descremada ", s)
    s = re.sub(
        r"\b0\s*%?\s*lactosa\b|\bsin\s+lactosa\b|\bdeslactosad[ao]s?\b|\breducid[ao]\s+en\s+lactosa\b",
        " zero_lactosa ",
        s,
    )
    if "zero_lactosa" in s:
        s = re.sub(r"\b(?:parcialmente\s+)?descremad[ao]s?\b", " ", s)
    s = re.sub(r"\bsin\s+azucar(?:es)?\b", " sin_azucar ", s)
    if re.search(r"\b(?:black|zero)\b", s):
        s = s.replace("sin_azucar", " ")

    # Quitar expresiones de medida ("1.5 l", "473 ml", "90 grs", "2%", "3%")
    s = re.sub(
        r"\b\d+(?:[.,]\d+)?\s*(?:l|lt|lts|litro|litros|ml|cc|cm3|g|gr|grs|gramos?|kg|kgs|kilos?|%|un|u|uni|unid|unidades)\b",
        " ",
        s,
    )
    # Quitar el "2" suelto de "Leche liviana 2 fortificada"
    s = re.sub(r"\bliviana\s+2\b", "liviana", s)

    raw_tokens = re.sub(r"[^a-z0-9_]+", " ", s).split()
    brand_tokens = set(brand_key.split())

    content_tokens: set[str] = set()
    for t in raw_tokens:
        t_mapped = _NUMBER_WORDS.get(t, t) if _NUMBER_WORDS.get(t) in brand_tokens else t
        if t_mapped in brand_tokens or t in _FILLER_TOKENS or t.isdigit() or len(t) <= 1:
            continue
        if t == "cola" and ("pepsi" in brand_tokens or "coca" in brand_tokens):
            continue
        content_tokens.add(_singularize_token(t))

    if not content_tokens:
        return None

    return (brand_key, round(cant, 3), u_norm, is_multipack, frozenset(content_tokens))


def _compatible_gs1_prefix(ean1: str, ean2: str) -> bool:
    """Si ambos son EAN-13 argentinos ('779...'), exige que compartan el prefijo de fabricante (primeros 7 dígitos)."""
    if ean1.isdigit() and ean2.isdigit() and len(ean1) == 13 and len(ean2) == 13:
        if ean1.startswith("779") and ean2.startswith("779"):
            return ean1[:7] == ean2[:7]
    return True


_PRODUCE_EXCLUDED_WORDS = {
    "pure", "salsa", "extracto", "fritas", "frita", "congeladas", "congelada", "congelado", "congelados",
    "chips", "jugo", "jugos", "mermelada", "dulce", "dulces", "galletita", "galletitas", "yogur", "yogurisimo",
    "postre", "postrecito", "helado", "bebida", "bebidas", "agua", "aguas", "cerveza", "cervezas",
    "semilla", "semillas", "lata", "latas", "conserva", "conservas", "tetrabrik", "tetra", "doypack",
    "shampoo", "acondicionador", "jabon", "nestum", "avena", "alfajor", "alfajores", "tortilla", "tortillas",
    "tapas", "empanadas", "empanada", "tarta", "tartas", "pelado", "cubeteado", "triturado", "polvo",
    "pan", "pancho", "hamburguesa", "noquis", "ravioles", "fideos", "snack", "snacks", "arroz",
    "rebozador", "premezcla", "harina", "bizcochuelo", "aceite", "vinagre", "aderezo", "mayonesa",
    "ketchup", "mostaza", "gelatina", "barra", "barrita", "chocolate", "bombones", "caramelos",
    "bocaditos", "rellenos", "relleno", "obleas", "turron", "turrón", "granola", "mix", "alimento",
    "pizza", "prepizza", "leberwurst", "salchicha", "salame", "queso", "embutido", "fiambre",
}

_PRODUCE_INDUSTRIAL_BRANDS = {
    "arcor", "knorr", "lay's", "lays", "mc cain", "la campagnola", "canale", "orali",
    "powerade", "gatorade", "levite", "cepita", "dahi", "yogurisimo", "menu box", "zummy",
    "cuisine y co", "cuisine & co", "pepitos", "traviata", "melitas", "mazza", "fargo",
    "artesano", "la salteña", "la saltena", "pringles", "integra", "9 de oro", "1891",
}

_PRODUCE_TAXONOMY = [
    # TOMATES
    ("tomate_perita", "Tomate Perita (x kg)", [r"\btomate\b.*\bperita\b"]),
    ("tomate_cherry", "Tomate Cherry (x kg)", [r"\btomate\b.*\bcherry\b"]),
    ("tomate_redondo", "Tomate Redondo (x kg)", [r"\btomate\b.*\b(redondo|platense|comun|grande)\b", r"\btomate\b"]),
    
    # PAPAS Y BATATAS
    ("papa_negra", "Papa Negra (x kg)", [r"\bpapa\b.*\bnegra\b"]),
    ("papa_blanca", "Papa Blanca (x kg)", [r"\bpapa\b.*\bblanca\b"]),
    ("papa_cepillada", "Papa Cepillada (x kg)", [r"\bpapa\b.*\b(cepillada|lavada)\b", r"\bpapa\b"]),
    ("batata", "Batata (x kg)", [r"\bbatata\b"]),

    # CEBOLLAS
    ("cebolla_morada", "Cebolla Morada (x kg)", [r"\bcebolla\b.*\bmorada\b"]),
    ("cebolla_verdeo", "Cebolla de Verdeo (x kg / atado)", [r"\b(cebolla\b.*\bverdeo|verdeo)\b"]),
    ("cebolla_comun", "Cebolla Común (x kg)", [r"\bcebolla\b"]),

    # BANANAS
    ("banana_ecuador", "Banana Ecuador Seleccionada (x kg)", [r"\bbanana\b.*\b(ecuador|cavendish|seleccion|premium)\b"]),
    ("banana_comun", "Banana Fresca (x kg)", [r"\b(banana|platano)\b"]),

    # MANZANAS
    ("manzana_verde", "Manzana Verde (x kg)", [r"\bmanzana\b.*\b(verde|granny)\b"]),
    ("manzana_roja", "Manzana Roja (x kg)", [r"\bmanzana\b.*\b(roja|deliciosa|red|pink lady|gala)\b", r"\bmanzana\b"]),

    # CITRICOS
    ("naranja_jugo", "Naranja para Jugo (x kg)", [r"\bnaranja\b.*\bjugo\b"]),
    ("naranja_ombligo", "Naranja de Ombligo (x kg)", [r"\bnaranja\b.*\b(ombligo|valencia)\b", r"\bnaranja\b"]),
    ("mandarina", "Mandarina (x kg)", [r"\bmandarina\b"]),
    ("limon", "Limón (x kg)", [r"\blimon\b"]),
    ("pomelo", "Pomelo (x kg)", [r"\bpomelo\b"]),

    # ZAPALLOS
    ("zapallo_anco", "Zapallo Anco / Calabaza (x kg)", [r"\b(zapallo\b.*\banco|calabaza|calabacin)\b"]),
    ("zapallo_cabutia", "Zapallo Cabutiá (x kg)", [r"\b(zapallo\b.*\bcabutia)\b"]),
    ("zapallo_redondo", "Zapallo Redondo (x kg)", [r"\bzapallo\b"]),

    # ZANAHORIAS
    ("zanahoria", "Zanahoria (x kg)", [r"\bzanahoria\b"]),

    # MORRONES
    ("morron_rojo", "Morrón Rojo (x kg)", [r"\b(morron|pimiento)\b.*\brojo\b"]),
    ("morron_verde", "Morrón Verde (x kg)", [r"\b(morron|pimiento)\b.*\bverde\b"]),
    ("morron_amarillo", "Morrón Amarillo (x kg)", [r"\b(morron|pimiento)\b.*\bamarillo\b"]),

    # HOJAS
    ("lechuga_criolla", "Lechuga Criolla (x kg)", [r"\blechuga\b.*\bcriolla\b"]),
    ("lechuga_mantecosa", "Lechuga Mantecosa (x kg)", [r"\blechuga\b.*\bmantecosa\b"]),
    ("lechuga_capuchina", "Lechuga Capuchina (x kg)", [r"\blechuga\b.*\b(capuchina|iceberg)\b"]),
    ("lechuga_comun", "Lechuga (x kg)", [r"\blechuga\b"]),
    ("acelga", "Acelga (x atado / kg)", [r"\bacelga\b"]),
    ("espinaca", "Espinaca (x atado / kg)", [r"\bespinaca\b"]),
    ("rucula", "Rúcula (x atado / kg)", [r"\brucula\b"]),

    # OTROS
    ("palta_hass", "Palta Hass (x kg / un)", [r"\bpalta\b"]),
    ("berenjena", "Berenjena (x kg)", [r"\bberenjena\b"]),
    ("zucchini", "Zucchini (x kg)", [r"\bzucchini\b"]),
    ("zapallito_verde", "Zapallito Redondo Verde (x kg)", [r"\bzapallito\b"]),
    ("pepino", "Pepino (x kg)", [r"\bpepino\b"]),
    ("choclo", "Choclo (x un / kg)", [r"\bchoclo\b"]),
    ("ajo", "Ajo (cabeza / x kg)", [r"\bajo\b"]),
    ("pera", "Pera Williams (x kg)", [r"\bpera\b"]),
    ("frutilla", "Frutilla (x kg / bandeja)", [r"\bfrutilla\b"]),
    ("durazno", "Durazno (x kg)", [r"\bdurazno\b"]),
    ("uva", "Uva (x kg)", [r"\buva\b"]),
]


def _match_produce(p: dict) -> tuple[str, str] | None:
    nom = _norm_text(p.get("nombre") or "")
    marca = _norm_text(p.get("marca") or "")
    tokens = set(nom.split())
    if tokens & _PRODUCE_EXCLUDED_WORDS:
        return None
    if marca in _PRODUCE_INDUSTRIAL_BRANDS:
        return None

    u = p.get("unidad_medida") or ""
    has_kg = (u == "kg" or "kg" in nom or "kilo" in nom or "granel" in nom or "atado" in nom or "bolsa" in nom)
    # Si el título indica gramos de paquete cerrado (ej: 160g, 450g) sin indicar kg, es producto industrial
    if re.search(r"\b\d+\s*g(?:r|rs|rm|rms)?\b", nom) and not has_kg:
        return None

    # En los supermercados, el código de barras comercial GS1 (779...) indica producto de fábrica empaquetado.
    # La fruta y verdura fresca usa códigos internos de balanza (20..29) o códigos de tienda (TN_, etc.)
    ean = str(p.get("ean") or "")
    if ean.startswith("779") and not ("granel" in nom or "cosecha" in nom or "seleccion" in nom or "bolsa" in nom):
        return None

    for key, display_name, patterns in _PRODUCE_TAXONOMY:
        for pat in patterns:
            if re.search(pat, nom):
                return key, display_name
    return None


_MEAT_EXCLUDED_WORDS = {
    "aromatizante", "repuesto", "glade", "repasador", "limpiador", "detergente", "jabon",
    "shampoo", "acondicionador", "babaganush", "salsa", "sal", "pimienta", "especias",
    "condimento", "carbon", "leña", "chips", "galletitas", "snack", "alfajor", "vino",
    "cerveza", "jugo", "gaseosa", "queso", "provoleta", "brie", "gouda", "pategras",
    "aceitunas", "pasta", "pepinillos", "pita", "bolsa para horno", "ajo", "especiado",
}

_MEAT_TAXONOMY = [
    # VACUNO
    ("tapa_asado", "Tapa de Asado (x kg)", [r"\btapa\s+de\s+asado\b"]),
    ("asado_tira", "Asado de Tira (x kg)", [r"\basado\b.*\b(tira|centro|banderita|tablita|medio|ventana)\b", r"\basado\b(?!.*\b(tapa|americano|cerdo|locos|sal)\b)"]),
    ("vacio", "Vacío (x kg)", [r"\b(vacio|vac[ií]o)\b"]),
    ("bife_chorizo", "Bife de Chorizo (x kg)", [r"\bbife[s]?\s+de\s+chorizo\b"]),
    ("ojo_bife", "Ojo de Bife (x kg)", [r"\bojo\s+de\s+bife\b"]),
    ("entrana", "Entraña (x kg)", [r"\b(entrana|entraña)\b"]),
    ("lomo", "Lomo Vacuno (x kg)", [r"\blomo\b(?!.*\b(cerdo|canadiense|bola|atun|atún|praga)\b)"]),
    ("colita_cuadril_cerdo", "Colita de Cuadril de Cerdo (x kg)", [r"\bcolita\s+de\s+cuadril\b.*\bcerdo\b"]),
    ("colita_cuadril", "Colita de Cuadril (x kg)", [r"\bcolita\s+de\s+cuadril\b"]),
    ("cuadril", "Cuadril (x kg)", [r"\bcuadril\b(?!.*\b(colita|tapa)\b)"]),
    ("matambre_cerdo", "Matambre de Cerdo (x kg)", [r"\bmatambre\b.*\bcerdo\b|\bmatambrito\b"]),
    ("matambre_vacuno", "Matambre Vacuno (x kg)", [r"\bmatambre\b"]),
    ("peceto", "Peceto (x kg)", [r"\bpeceto\b"]),
    ("nalga", "Nalga para Milanesa (x kg)", [r"\bnalga\b(?!.*\bcerdo\b)"]),
    ("bola_lomo", "Bola de Lomo (x kg)", [r"\bbola\s+de\s+lomo\b"]),
    ("cuadrada", "Cuadrada para Milanesa (x kg)", [r"\bcuadrada\b"]),
    ("picada_especial", "Carne Picada Especial (x kg)", [r"\b(carne\s+picada|picada)\b.*\b(especial|magra|seleccion|primera)\b"]),
    ("picada_comun", "Carne Picada Común (x kg)", [r"\bcarne\s+picada\b"]),
    ("bondiola", "Bondiola de Cerdo (x kg)", [r"\bbondiola\b"]),
    ("pechito_cerdo", "Pechito de Cerdo (x kg)", [r"\bpechito\s+de\s+cerdo\b"]),
    ("costillita_cerdo", "Costillitas de Cerdo (x kg)", [r"\b(costillita|costillitas|carre|carré)\s+de\s+cerdo\b"]),
    ("solomillo_cerdo", "Solomillo de Cerdo (x kg)", [r"\bsolomillo\b"]),
    ("pechuga_pollo", "Pechuga de Pollo / Suprema (x kg)", [r"\b(pechuga|suprema)\b.*\bpollo\b|\bpechuga\b|\bsuprema\b"]),
    ("pata_muslo", "Pata y Muslo de Pollo (x kg)", [r"\bpata\s+y\s+muslo\b|\bcuarto\s+trasero\b"]),
    ("pollo_entero", "Pollo Entero Fresco (x kg)", [r"\bpollo\s+entero\b|\bpollo\s+fresco\b"]),
    ("chorizo_parrillero", "Chorizo Parrillero (x kg)", [r"\bchorizo\b(?!.*\b(bife|colorado|seco|espanol|español)\b)"]),
    ("morcilla", "Morcilla (x kg)", [r"\bmorcilla\b"]),
]


def _match_meat(p: dict) -> tuple[str, str] | None:
    nom = _norm_text(p.get("nombre") or "")
    tokens = set(nom.split())
    if tokens & _MEAT_EXCLUDED_WORDS:
        return None
    # Si indica gramos pequeños de paquete cerrado (ej: 60g, 150g) sin indicar kg, es producto de almacén
    if re.search(r"\b\d+\s*g(?:r|rs|rm|rms)?\b", nom) and not ("kg" in nom or "kilo" in nom):
        return None

    # Normalizar descriptores de empaque "al vacio" para no confundir con el corte Vacío
    clean_nom = re.sub(r"\b(?:envasad[ao]s?\s+)?al\s+vac[ií]o\b", " ", nom)
    clean_nom = re.sub(r"\benv\s+al\s+vac[ií]o\b", " ", clean_nom)
    clean_nom = " ".join(clean_nom.split())

    for key, display_name, patterns in _MEAT_TAXONOMY:
        for pat in patterns:
            target = clean_nom if key == "vacio" else nom
            if re.search(pat, target):
                return key, display_name
    return None


def _store_in_memory(flat_products: list[dict]) -> list[dict]:
    """Agrupa en memoria por EAN, unifica frutas/verduras y cortes de carnicería en identidades canónicas,
    fusiona EANs gemelos del mismo fabricante/variante/tamaño y guarda en RAM."""
    by_ean: dict[str, dict] = {}
    for d in flat_products:
        if not d.get("ean") or not d.get("precio_venta") or int(d.get("stock") or 0) <= 0:
            continue

        prod_match = _match_produce(d)
        meat_match = _match_meat(d) if not prod_match else None
        if prod_match:
            canon_key, display_title = prod_match
            ean = f"PRODUCE_{canon_key.upper()}"
            d_nom = display_title
            d_marca = "Verdulería"
        elif meat_match:
            canon_key, display_title = meat_match
            ean = f"MEAT_{canon_key.upper()}"
            d_nom = display_title
            d_marca = "Carnicería"
        else:
            ean = str(d["ean"])
            d_nom = (d.get("nombre") or "").strip()
            d_marca = (d.get("marca") or "").strip()

        is_canonical_fresh = bool(prod_match or meat_match)

        g = by_ean.setdefault(ean, {
            "ean": ean,
            "nombre": d_nom if is_canonical_fresh else (d.get("nombre") or ""),
            "marca": d_marca if is_canonical_fresh else (d_marca if _is_valid_brand(d_marca) else "Genérico"),
            "imagen": d.get("imagen") or "",
            "offers_by_store": {},
            "all_names": set(),
        })

        orig_nom = (d.get("nombre") or "").strip()
        if orig_nom:
            g["all_names"].add(orig_nom)
            if not is_canonical_fresh and ("24.7" in orig_nom or "24 7" in orig_nom) and not ("24.7" in g["nombre"] or "24 7" in g["nombre"]):
                g["nombre"] = orig_nom
        if not g["imagen"] and d.get("imagen"):
            g["imagen"] = d["imagen"]
        if not _is_valid_brand(g["marca"]) and _is_valid_brand(d_marca):
            g["marca"] = d_marca

        offer = _to_offer_dict(d)
        if is_canonical_fresh and d["supermercado"] in g["offers_by_store"]:
            existing = g["offers_by_store"][d["supermercado"]]
            p_exist = existing.get("unit_price") or existing.get("precio") or float("inf")
            p_new = offer.get("unit_price") or offer.get("precio") or float("inf")
            if p_new < p_exist:
                g["offers_by_store"][d["supermercado"]] = offer
        else:
            g["offers_by_store"][d["supermercado"]] = offer

    # Segunda pasada genérica: fusionar grupos con distinto EAN pero idéntica firma canónica
    # (Misma marca + Mismo peso/volumen + Mismos tokens de producto/variante + Cadenas disjuntas + Mismo prefijo GS1)
    ean_list = sorted(
        by_ean.keys(),
        key=lambda e: (-len(by_ean[e]["offers_by_store"]), e),
    )
    by_sig: dict[tuple, list[str]] = {}
    merged_away: set[str] = set()

    for ean in ean_list:
        if ean.startswith(("PRODUCE_", "MEAT_")):
            continue
        g = by_ean[ean]
        sig = _canonical_signature(g["nombre"], g["marca"])
        if not sig:
            continue
        candidates = by_sig.get(sig, [])
        merged = False
        for primary_ean in candidates:
            if primary_ean in merged_away:
                continue
            primary_g = by_ean[primary_ean]
            # 1. Ningún supermercado puede repetirse entre ambos grupos
            if not set(primary_g["offers_by_store"].keys()).isdisjoint(g["offers_by_store"].keys()):
                continue
            # 2. Prefijo de fabricante GS1 compatible
            if not _compatible_gs1_prefix(primary_ean, ean):
                continue
            # 3. Coherencia de precios (evitar unir un bulto mal rotulado con una unidad)
            p_main = min(o["precio"] for o in primary_g["offers_by_store"].values())
            p_cand = min(o["precio"] for o in g["offers_by_store"].values())
            if not (0.45 <= (p_cand / p_main) <= 2.2):
                continue

            # Fusionar ofertas dentro del grupo principal
            for st, off in g["offers_by_store"].items():
                primary_g["offers_by_store"][st] = off
            primary_g.setdefault("all_names", set()).update(g.get("all_names") or [])
            if not primary_g["imagen"] and g["imagen"]:
                primary_g["imagen"] = g["imagen"]
            _EAN_ALIASES.setdefault(primary_ean, set()).add(ean)
            merged_away.add(ean)
            merged = True
            break

        if not merged:
            by_sig.setdefault(sig, []).append(ean)

    groups: list[dict] = []
    for ean, g in by_ean.items():
        if ean in merged_away:
            continue
        cant, u_tit = extraer_unidad_titulo(g["nombre"])
        offers = list(g["offers_by_store"].values())
        if not ean.startswith(("PRODUCE_", "MEAT_")):
            for o in offers:
                # Solo aplicar descuento al precio unitario ($/l, $/kg, $/un) si la promo es abierta a todo público
                eff_p = (
                    float(o["precio"])
                    if o.get("requires_club")
                    else float(o.get("promo_unit_price") or o["precio"])
                )
                if cant > 0:
                    p_u, u_norm = normalizar_unidad(eff_p / cant, u_tit)
                    o["unit_price"] = sanity_precio_unidad(eff_p, p_u, u_norm)
                    o["unit_measure"] = u_norm

        # Persistir en el catálogo en memoria de la sesión para el optimizador Smart Cart
        _LIVE_PRODUCTS_MEM[ean] = {
            "ean": ean,
            "nombre": g["nombre"],
            "marca": g["marca"],
            "imagen": g["imagen"],
        }
        mem_offers = _LIVE_OFFERS_MEM.setdefault(ean, {})
        for st, off in g["offers_by_store"].items():
            mem_offers[st] = {**off, "ean": ean, "nombre": g["nombre"]}

        if ean.startswith(("MEAT_", "PRODUCE_")):
            _LIVE_PRODUCTS_MEM[ean.lower()] = _LIVE_PRODUCTS_MEM[ean]
            _LIVE_OFFERS_MEM[ean.lower()] = mem_offers
            if "CHORIZO" in ean:
                _LIVE_OFFERS_MEM["MEAT_CHORIZO"] = mem_offers
                _LIVE_OFFERS_MEM["meat_chorizo"] = mem_offers
                _LIVE_PRODUCTS_MEM["MEAT_CHORIZO"] = _LIVE_PRODUCTS_MEM[ean]
                _LIVE_PRODUCTS_MEM["meat_chorizo"] = _LIVE_PRODUCTS_MEM[ean]
            if "ASADO_TIRA" in ean:
                _LIVE_OFFERS_MEM["MEAT_ASADO"] = mem_offers
                _LIVE_OFFERS_MEM["meat_asado"] = mem_offers

        groups.append({
            "ean": ean,
            "nombre": g["nombre"],
            "marca": g["marca"],
            "imagen": g["imagen"],
            "offers": offers,
            "all_names": list(g.get("all_names") or []),
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

    async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
        vtex_names = [
            st for st in LIVE_VTEX_DOMAINS.keys()
            if region_map.get(st) != "__NO_DELIVERY__"
        ]
        is_ean = q_norm.isdigit() and 8 <= len(q_norm) <= 14
        if is_ean:
            # Búsqueda exacta indexada por EAN directo en cada cadena VTEX
            tasks = [
                fetch_vtex_by_eans_live(
                    client,
                    st,
                    [q_norm],
                    region_id=region_map.get(st),
                )
                for st in vtex_names
            ]
        else:
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
        tiendanube_names = list(TIENDANUBE_DOMAINS.keys())
        for tn_st in tiendanube_names:
            tasks.append(fetch_tiendanube_live(client, tn_st, q_norm, limit=10))
        woocommerce_names = list(WOOCOMMERCE_DOMAINS.keys())
        for wc_st in woocommerce_names:
            tasks.append(fetch_woocommerce_live(client, wc_st, q_norm, limit=10))
        tasks.append(fetch_mercadolibre_live(client, q_norm, limit=12))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_names = vtex_names + ["Coto"] + shopify_names + tiendanube_names + woocommerce_names + ["MercadoLibre"]
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
        # + Re-consulta automática a Coto si VTEX Intelligent Search corrigió un error de tipeo (ej. 'pecsi' -> 'pepsi')
        vtex_only_prods = [p for p in flat_products if p.get("supermercado") != "Coto"]
        corrected_q = _detect_corrected_query(q_norm, vtex_only_prods)

        top_eans = ean_priority[:22]
        ean_tasks = []
        ean_task_stores = []
        if top_eans and not q_norm.isdigit():
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

        if corrected_q and corrected_q != q_norm:
            ean_tasks.append(fetch_coto_live(client, corrected_q, limit=limit_per_store))
            ean_task_stores.append("Coto")

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
    sort_by: str = "unit_price_asc",
    only_offers: bool = False,
    cp: str | None = None,
) -> list[dict]:
    """Devuelve los grupos de productos 100% desde la búsqueda en vivo (sin base de datos),
    filtrando falsos positivos de subcadena (ej. 'Pepsina' al buscar 'Pepsi') y ordenando
    de arriba hacia abajo por el precio por litro/kilo/unidad más conveniente.
    """
    q_clean = query.strip()
    effective_q = q_clean if len(q_clean) >= 2 else "coca cola leche"
    res = await live_search_and_sync(
        effective_q, limit_per_store=18, only_offers=only_offers, cp=cp
    )
    raw_groups = [
        {
            **g,
            "offers": list(g["offers"]),
        }
        for g in res.get("groups", [])
    ]

    # 1. Filtro estricto por palabra completa (evita 'Pepsina' o 'Cerveza Imperial' al buscar 'Pepsi',
    #    o 'Bastones' al buscar 'Stones')
    _STOP = {"de", "del", "la", "el", "los", "las", "con", "sin", "en", "para", "por", "al", "y", "o", "x"}
    q_words = [w for w in _norm_text(q_clean).split() if w not in _STOP and len(w) >= 2]

    if q_clean.isdigit():
        # Búsqueda estricta por código de barras: solo productos que coincidan con este EAN exacto
        groups = [
            g for g in raw_groups
            if g["ean"] == q_clean or any(o.get("ean") == q_clean for o in g.get("offers", []))
        ]
    elif q_words:
        q_sings = [_singularize_token(_NUMBER_WORDS.get(w, w)) for w in q_words]

        def _matches_strict(g: dict) -> bool:
            all_text = f"{g['nombre']} {g['marca']} " + " ".join(g.get("all_names") or [])
            doc_tokens = _norm_text(all_text).split()
            doc_sings = {_singularize_token(_NUMBER_WORDS.get(t, t)) for t in doc_tokens}
            doc_raw = set(doc_tokens)
            for qw, qs in zip(q_words, q_sings):
                if qw not in doc_raw and qs not in doc_sings:
                    return False
            return True

        strict_groups = [g for g in raw_groups if _matches_strict(g)]
        if strict_groups:
            groups = strict_groups
        else:
            # Si no hubo coincidencias exactas porque el usuario tipeó mal (ej. 'pecsi', 'hugies', 'matarazo'),
            # permitimos tolerancia ortográfica Damerau-Levenshtein (distancia <= 1 o 2 en palabras del mismo largo)
            def _matches_fuzzy_typo(g: dict) -> bool:
                all_text = f"{g['nombre']} {g['marca']} " + " ".join(g.get("all_names") or [])
                doc_tokens = _norm_text(all_text).split()
                for qw in q_words:
                    max_d = 1 if len(qw) <= 5 else 2
                    if not any(
                        abs(len(dt) - len(qw)) <= 1 and _edit_distance(qw, dt) <= max_d
                        for dt in doc_tokens
                    ):
                        return False
                return True

            fuzzy_groups = [g for g in raw_groups if _matches_fuzzy_typo(g)]
            groups = fuzzy_groups if fuzzy_groups else raw_groups
    else:
        groups = raw_groups

    if only_offers:
        groups = [
            g for g in groups
            if any(
                (o.get("discount") or 0) >= 5
                or (o.get("promo_label") and not o.get("requires_club"))
                for o in g["offers"]
            )
        ]

    first_tok = _singularize_token(q_words[0]) if q_words else ""

    def _public_eff(o: dict) -> float:
        return float(o["precio"]) if o.get("requires_club") else float(o.get("promo_unit_price") or o["precio"])

    for g in groups:
        if sort_by == "unit_price_asc":
            g["offers"].sort(
                key=lambda o: (
                    o.get("unit_price") is None,
                    o.get("unit_price") or 999999,
                    _public_eff(o),
                )
            )
        else:
            g["offers"].sort(key=_public_eff)

    def _group_sort_key(g: dict):
        name_tokens = [_singularize_token(t) for t in _norm_text(g["nombre"]).split()]
        brand_tokens = {_singularize_token(t) for t in _norm_text(g["marca"]).split()}

        # Tier 0: El producto ES de esa marca (ej. marca 'PEPSI') o su nombre empieza con lo buscado (ej. 'Leche...')
        # Tier 1: Productos secundarios que contienen la palabra más adelante (ej. 'Dulce de leche' al buscar 'leche')
        if q_words:
            is_brand_match = all(_singularize_token(w) in brand_tokens for w in q_words)
            starts_with_query = bool(name_tokens and name_tokens[0] == first_tok)
            tier = 0 if (is_brand_match or starts_with_query) else 1
        else:
            tier = 0

        best_p = min(_public_eff(o) for o in g["offers"]) if g["offers"] else 999999
        best_u = min(
            (o.get("unit_price") or _public_eff(o))
            for o in g["offers"]
        ) if g["offers"] else 999999

        if sort_by == "unit_price_asc":
            return (tier, best_u, best_p, -len(g["offers"]))
        return (tier, best_p, best_u, -len(g["offers"]))

    groups.sort(key=_group_sort_key)
    return groups


_MEAT_CANONICAL_ALIASES = {
    "MEAT_CHORIZO": "MEAT_CHORIZO_PARRILLERO",
    "MEAT_CHORIZO_CERDO": "MEAT_CHORIZO_PARRILLERO",
    "MEAT_BIFE": "MEAT_BIFE_CHORIZO",
    "MEAT_TAPA": "MEAT_TAPA_ASADO",
    "MEAT_PATA": "MEAT_PATA_MUSLO",
    "MEAT_POLLO": "MEAT_POLLO_ENTERO",
    "MEAT_CARNE_PICADA": "MEAT_PICADA_COMUN",
    "MEAT_PICADA": "MEAT_PICADA_COMUN",
}


def _clean_product_title_for_sync(nom: str) -> str:
    t = re.sub(r"\(.*?\)", "", nom)
    t = re.sub(r"\b(?:x\s*kg|kilo|litros?|lts?|cc\.?)\b", "", t, flags=re.I)
    return " ".join(t.split()).strip()


async def live_offers_for_eans(
    eans: list[str],
    cp: str | None = None,
    names_hint: dict[str, str] | None = None,
):
    """Obtiene en vivo las ofertas para los EANs de Mi Lista (Smart Cart), completando desde VTEX si falta alguno."""
    if not eans:
        return {}, {}

    names_hint = names_hint or {}

    def _resolve_mem(e: str):
        if e in _LIVE_OFFERS_MEM:
            return _LIVE_OFFERS_MEM[e]
        eu = e.upper()
        if eu in _LIVE_OFFERS_MEM:
            return _LIVE_OFFERS_MEM[eu]
        el = e.lower()
        if el in _LIVE_OFFERS_MEM:
            return _LIVE_OFFERS_MEM[el]
        alias = _MEAT_CANONICAL_ALIASES.get(eu)
        if alias and alias in _LIVE_OFFERS_MEM:
            return _LIVE_OFFERS_MEM[alias]
        if "CHORIZO" in eu and "MEAT_CHORIZO_PARRILLERO" in _LIVE_OFFERS_MEM:
            return _LIVE_OFFERS_MEM["MEAT_CHORIZO_PARRILLERO"]
        return None

    missing_eans = [e for e in eans if not _resolve_mem(e)]
    digit_eans = [e for e in missing_eans if e.isdigit()]
    non_digit = [e for e in missing_eans if not e.isdigit()]

    sync_tasks = []
    if digit_eans:
        sync_tasks.append(live_lookup_eans(digit_eans, cp=cp))

    for e in non_digit:
        eu = e.upper()
        term = ""
        if eu.startswith("PRODUCE_"):
            term = eu.replace("PRODUCE_", "").replace("_", " ")
        elif eu.startswith("MEAT_"):
            alias = _MEAT_CANONICAL_ALIASES.get(eu, eu)
            term = alias.replace("MEAT_", "").replace("_", " ")
        if term:
            sync_tasks.append(live_search_and_sync(term, limit_per_store=4, cp=cp))

    # Fallback sync con término limpio para productos que no están en memoria
    for e in digit_eans:
        if names_hint.get(e):
            clean_term = _clean_product_title_for_sync(names_hint[e])
            if clean_term:
                sync_tasks.append(live_search_and_sync(clean_term, limit_per_store=3, cp=cp))

    if sync_tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*sync_tasks, return_exceptions=True), timeout=9.0)
        except Exception:
            pass

    # Post-proceso: mapear a digit eans si se encontraron ofertas por búsqueda de título
    for e in eans:
        if not _resolve_mem(e) and names_hint.get(e):
            nom_words = [w for w in _norm_text(names_hint[e]).split() if len(w) >= 3][:3]
            for mem_ean, offs in _LIVE_OFFERS_MEM.items():
                if not offs:
                    continue
                s_nom = _norm_text(list(offs.values())[0].get("nombre") or "")
                if all(w in s_nom for w in nom_words):
                    _LIVE_OFFERS_MEM[e] = offs
                    break

    out: dict[str, list[dict]] = {}
    names: dict[str, str] = {}
    for ean in eans:
        prod_info = _LIVE_PRODUCTS_MEM.get(ean) or _LIVE_PRODUCTS_MEM.get(ean.upper())
        if prod_info:
            names[ean] = prod_info["nombre"]
        store_map = _resolve_mem(ean)
        if store_map:
            out[ean] = list(store_map.values())
            if ean not in names and out[ean]:
                names[ean] = out[ean][0].get("nombre") or ean
        if ean not in names and names_hint.get(ean):
            names[ean] = names_hint[ean]
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
