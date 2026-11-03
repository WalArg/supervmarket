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
    _safe_int,
    _safe_float,
)
from .normalization import (  # noqa: E402
    is_valid_ean13,
    normalize_ean,
    is_internal_scale,
    extract_canonical_model,
    canonical_model_key,
    is_accessory,
)
from .stores import (  # noqa: E402
    VTEX_DOMAINS,
    VTEX_SALES_CHANNELS,
    supports_cart,
    store_vertical,
    is_marketplace,
    STORE_REGISTRY,
)
from . import regions as regions_mod                                              # noqa: E402
from .mercadolibre import fetch_mercadolibre_live                                # noqa: E402

LIVE_VTEX_DOMAINS: dict[str, str] = {
    **VTEX_DOMAINS,
    "TheFoodMarket": "https://www.thefoodmarket.com.ar",
    "Oster": "https://www.osterargentina.com",
    "StyleStore": "https://www.stylestore.com.ar",
}

SHOPIFY_DOMAINS: dict[str, str] = {
    "LaBarraCCU": "https://labarraccu.com.ar",
    "Bodegas Bianchi": "https://www.bodegasbianchi.com.ar",
    "BodegasBianchi": "https://www.bodegasbianchi.com.ar",
}

TIENDANUBE_DOMAINS: dict[str, str] = {
    "LaBarata": "https://labarata.ar",
    "TonelPrivado": "https://www.tonelprivado.com",
    "DePastura": "https://tienda.depastura.com.ar",
}

WOOCOMMERCE_DOMAINS: dict[str, str] = {
    "ArcorEnCasa": "https://arcorencasa.com",
}

SUPERMARKET_CHAINS = (
    "Jumbo", "Disco", "Vea", "Carrefour", "Dia", "Masonline",
    "Josimar", "Toledo", "Cordiez",
)

ELECTRO_MARKETPLACE_CHAINS = (
    "Provincia Compras", "On City", "Fravega", "Cetrogar",
    "Naldo", "Pardo", "Coppel", "Samsung", "Philips", "Whirlpool",
    "Moulinex", "Sony", "Easy", "Musimundo", "Oster", "StyleStore",
)

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
    grocery_only: bool = False,
    store_type: str | None = None,
) -> list[dict]:
    domain = LIVE_VTEX_DOMAINS.get(store)
    if not domain:
        return []
    base = domain if domain.startswith("http") else f"https://{domain}"
    sc = str(VTEX_SALES_CHANNELS.get(store, "1"))
    sc_qs = f"&sc={sc}" if sc != "1" else ""
    st_type = store_type or store_vertical(store)

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
                if (p := parse_vtex_product(raw, store, grocery_only=grocery_only, store_type=st_type)) and int(p.get("stock") or 0) > 0
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
                    if (p := parse_vtex_product(raw, store, grocery_only=grocery_only, store_type=st_type)) and int(p.get("stock") or 0) > 0
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
            if (p := parse_vtex_product(raw, store, grocery_only=grocery_only, store_type=st_type)) and int(p.get("stock") or 0) > 0
        ]
    except Exception:
        return []


async def fetch_vtex_by_eans_live(
    client: httpx.AsyncClient,
    store: str,
    eans: list[str],
    region_id: str | None = None,
    grocery_only: bool = False,
    store_type: str | None = None,
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
    st_type = store_type or store_vertical(store)
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
            parsed = parse_vtex_product(raw_prod, store, grocery_only=grocery_only, store_type=st_type)
            if parsed and int(parsed.get("stock") or 0) > 0:
                out.append(parsed)
        return out
    except Exception:
        return []


async def fetch_coto_live(
    client: httpx.AsyncClient,
    query: str,
    limit: int = 24,
    grocery_only: bool = False,
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
                    parsed = parse_coto_record(rec, grocery_only=grocery_only)
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


BAD_VTEX_IMAGE_PATTERNS = (
    "607590",
    "879659",
    "843734",
    "ids/314352",
    "ids/345227",
)

_IMAGE_STORE_RELIABILITY: dict[str, int] = {
    "Carrefour": 0,
    "Dia": 1,
    "Jumbo": 2,
    "Disco": 3,
    "Vea": 4,
    "Masonline": 5,
    "Coto": 6,
    "MercadoLibre": 7,
}


def _clean_image_url(url: str | None) -> str:
    """Filtra URLs de imagen inválidas (no HTTPS) o en lista negra de IDs de VTEX rotos/erróneos."""
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    if u.startswith("//"):
        u = "https:" + u
    if not u.startswith("https://"):
        return ""
    if any(bad in u for bad in BAD_VTEX_IMAGE_PATTERNS):
        return ""
    return u


def _build_gallery_images(offers: list[dict], fallback_img: str = "") -> list[str]:
    """Construye la galería de imágenes válidas HTTPS distintas ordenadas por confiabilidad de cadena."""
    sorted_offers = sorted(
        offers,
        key=lambda o: _IMAGE_STORE_RELIABILITY.get(str(o.get("supermercado") or ""), 99),
    )
    gallery: list[str] = []
    seen: set[str] = set()
    for off in sorted_offers:
        img = _clean_image_url(off.get("imagen"))
        if img and img not in seen:
            seen.add(img)
            gallery.append(img)
    fb = _clean_image_url(fallback_img)
    if fb and fb not in seen:
        gallery.append(fb)
    return gallery


_SEMANTIC_MUTUALLY_EXCLUSIVE_PAIRS: list[tuple[set[str], set[str]]] = [
    # 1. Vinos y espumantes vs Lácteos / Quesos / Cremas / Leche
    (
        {
            "vino", "vinos", "malbec", "cabernet", "merlot", "syrah", "bonarda",
            "chardonnay", "sauvignon", "torrontes", "espumante", "champagne", "bodega",
        },
        {
            "queso", "quesos", "crema", "yogur", "yogurt", "yogurisimo", "manteca",
            "leche", "ricota", "muzzarella", "mozzarella", "casancrem", "mendicrim",
            "finlandia", "untable", "postrecito",
        },
    ),
    # 2. Galletitas vs Alfajores / Helados
    (
        {"galletita", "galletitas", "galleta", "galletas", "cracker", "crackers", "tostada", "tostadas"},
        {"alfajor", "alfajores", "helado", "helados"},
    ),
    # 3. Limpieza / Desodorante vs Maquillaje / Cosmética
    (
        {
            "detergente", "jabon liquido", "jabon en polvo", "lavandina", "desodorante",
            "antitranspirante", "limpiador", "desinfectante", "suavizante", "quitamanchas",
            "desengrasante", "insecticida", "lustramuebles", "papel higienico", "rollo de cocina",
        },
        {
            "mascara de pestanas", "mascara pestanas", "mascara para pestanas", "pestanas",
            "pestana", "rimel", "labial", "maquillaje", "esmalte", "delineador", "rubor",
            "sombra", "corrector", "base fluida",
        },
    ),
    # 4. Aceite comestible (girasol/oliva/maíz/cocina) vs Aceite motor / Lubricante / Automotor
    (
        {
            "girasol", "oliva", "maiz", "canola", "soja", "comestible", "cocina",
            "mezcla", "natura", "cocinero", "canuelas", "lira", "legitimo", "patito",
            "molinos", "morixe", "pureza", "vinagre", "mayonesa", "ensalada",
        },
        {
            "aceite motor", "aceite de motor", "aceite para motor", "motor", "lubricante",
            "lubricantes", "auto", "autos", "automotor", "sintetico", "semisintetico",
            "multigrado", "10w40", "15w40", "5w30", "5w40", "20w50", "4t", "2t",
            "anticongelante", "refrigerante", "elaion", "motul", "castrol", "helix",
        },
    ),
    # 5. Alimentos / Bebidas humanas vs Limpieza / Cosmética / Mascotas / Automotor
    (
        {
            "vino", "malbec", "cabernet", "espumante", "cerveza", "gaseosa", "jugo",
            "galletita", "galletitas", "alfajor", "helado", "fideos", "arroz", "harina",
            "azucar", "yerba", "cafe", "pan", "manteca", "yogur", "queso", "mayonesa",
            "ketchup", "mostaza", "atun", "mermelada", "dulce de leche",
        },
        {
            "detergente", "lavandina", "limpiador", "desinfectante", "suavizante",
            "quitamanchas", "desengrasante", "insecticida", "shampoo", "acondicionador",
            "desodorante", "antitranspirante", "dentifrico", "mascara de pestanas",
            "pestanas", "rimel", "labial", "maquillaje", "esmalte", "delineador",
            "papel higienico", "rollo de cocina", "panal", "panales", "aceite motor",
            "lubricante", "perro", "perros", "gato", "gatos", "mascota", "mascotas",
        },
    ),
]

_STRICT_SINGLE_TYPE_MARKERS: list[set[str]] = [
    {"alfajor", "alfajores"},
    {"helado", "helados"},
    {"mascara de pestanas", "mascara pestanas", "pestanas", "pestana", "rimel"},
    {"labial", "esmalte", "delineador", "maquillaje"},
    {"detergente"},
    {"lavandina"},
    {"aceite motor", "aceite de motor", "lubricante", "lubricantes", "10w40", "15w40", "5w30", "5w40", "20w50"},
]


def _matches_kw_set(norm_str: str, tokens: set[str], kw_set: set[str]) -> bool:
    for kw in kw_set:
        if " " in kw:
            if re.search(rf"\b{re.escape(kw)}\b", norm_str):
                return True
        elif kw in tokens:
            return True
    return False


def _is_semantically_coherent(group_name: str, candidate_name: str) -> bool:
    """Verifica coherencia semántica y de categoría entre el nombre del grupo y un candidato.
    Previene que un supermercado con un EAN mal cargado mezcle categorías incompatibles
    (ej: alfajor con galletitas Oreo, queso crema con vino, rímel con detergente, aceite comestible con aceite motor).
    """
    if not group_name or not candidate_name:
        return True
    n1 = " ".join(_norm_text(group_name).split())
    n2 = " ".join(_norm_text(candidate_name).split())
    if not n1 or not n2 or n1 == n2:
        return True

    t1 = set(n1.split())
    t2 = set(n2.split())

    # 1. Pares de conjuntos de palabras clave mutuamente excluyentes
    for set_a, set_b in _SEMANTIC_MUTUALLY_EXCLUSIVE_PAIRS:
        m1_a = _matches_kw_set(n1, t1, set_a)
        m1_b = _matches_kw_set(n1, t1, set_b)
        m2_a = _matches_kw_set(n2, t2, set_a)
        m2_b = _matches_kw_set(n2, t2, set_b)
        if (m1_a and m2_b and not m1_b) or (m1_b and m2_a and not m1_a):
            return False

    # 2. Caso especial: 'aceite' sin palabra automotriz vs 'aceite motor' / 'lubricante' / 'auto'
    auto_kws = _SEMANTIC_MUTUALLY_EXCLUSIVE_PAIRS[3][1]
    has_auto_1 = _matches_kw_set(n1, t1, auto_kws)
    has_auto_2 = _matches_kw_set(n2, t2, auto_kws)
    if has_auto_1 != has_auto_2:
        return False

    # 3. Marcadores estrictos de tipo de producto (ej. alfajor vs no-alfajor, helado vs no-helado, rímel vs no-rímel)
    for marker_set in _STRICT_SINGLE_TYPE_MARKERS:
        in_1 = _matches_kw_set(n1, t1, marker_set)
        in_2 = _matches_kw_set(n2, t2, marker_set)
        if in_1 != in_2:
            return False

    return True


def _to_offer_dict(d: dict) -> dict:
    precio = float(d["precio_venta"])
    p_lista = float(d.get("precio_lista") or precio)
    if p_lista > precio * 4.0 or p_lista < precio:
        p_lista = precio
        descuento = 0.0
    else:
        descuento = float(d.get("descuento") or 0.0)
    promo_unit = float(d.get("precio_promo_unit") or precio)
    offer_imagen = _clean_image_url(d.get("imagen"))

    seller_id = str(d.get("seller_id") or "1")
    raw_link = d.get("link") or ""
    # Enriquecer link con seller dinámico si no lo tiene y no es el seller principal
    if seller_id != "1" and raw_link and "seller=" not in raw_link:
        sep = "&" if "?" in raw_link else "?"
        final_link = f"{raw_link}{sep}seller={seller_id}"
    else:
        final_link = raw_link

    sku_id = str(d.get("itemId") or d.get("sku") or "")
    st_name = d["supermercado"]

    # Construir link directo de agregado al carrito si la tienda soporta guest-link
    cart_link = None
    if supports_cart(st_name) and sku_id:
        sc = str(VTEX_SALES_CHANNELS.get(st_name, "1"))
        base_domain = LIVE_VTEX_DOMAINS.get(st_name) or VTEX_DOMAINS.get(st_name)
        if base_domain:
            cart_link = f"{base_domain}/checkout/cart/add?sku={sku_id}&qty=1&seller={seller_id}&sc={sc}"

    return {
        "supermercado": st_name,
        "precio": precio,
        "precio_lista": p_lista,
        "precio_promo_unit": promo_unit,
        "stock": int(d.get("stock") or 0) > 0,
        "disponible": int(d.get("stock") or 0) > 0,
        "link": final_link,
        "cart_link": cart_link,
        "imagen": offer_imagen,
        "sku_id": sku_id,
        "seller_id": seller_id,
        "seller_name": d.get("seller_name") or "",
        "store_type": str(d.get("store_type") or store_vertical(st_name)),
        "modelo": d.get("modelo") or "",
        "tipo": d.get("tipo") or "",
        "unit_price": d.get("unit_price") or d.get("precio_por_unidad"),
        "unit_measure": d.get("unit_type") or d.get("unidad_medida") or "un",
        "discount": descuento,
        "promo_label": d.get("promo_label") or d.get("promo_etiqueta"),
        "promo_type": d.get("promo_tipo"),
        "promo_min_qty": int(d.get("promo_min_qty") or 1),
        "promo_unit_price": promo_unit,
        "requires_club": bool(d.get("requires_club") or d.get("requiere_club")),
        "supports_cart": supports_cart(st_name),
        "unit_multiplier": float(d.get("unit_multiplier") or 1.0),
        "nombre": d.get("nombre") or "",
        "cuotas": int(d.get("cuotas") or 1),
        "sin_interes": bool(d.get("sin_interes")),
        "cuotas_info": d.get("cuotas_info"),
        "cuota_monto": d.get("cuota_monto"),
        # Metadata enriquecida de Mercado Libre y Marketplace
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
_EAN_TO_MODEL: dict[str, str] = {}
_MODEL_TO_EAN: dict[str, str] = {}
_EAN_ALIASES: dict[str, set[str]] = {}
_MODEL_ALIASES: dict[str, set[str]] = {}


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
    "spiedo", "rotiseria", "rotisera", "sandwich", "sandwiches", "empanada", "empanadas", "tarta", "tartas",
}

_MEAT_TAXONOMY = [
    # CERDO ESPECÍFICOS (evaluados antes o con discriminación estricta para no mezclarse con vacuno)
    ("vacio_cerdo", "Vacío de Cerdo (x kg)", [r"\b(vacio|vac[ií]o)\b.*\bcerdo\b|\bcerdo\b.*\b(vacio|vac[ií]o)\b"]),
    ("entrana_cerdo", "Entraña de Cerdo (x kg)", [r"\b(entrana|entraña)\b.*\bcerdo\b|\bcerdo\b.*\b(entrana|entraña)\b"]),
    ("tapa_asado_cerdo", "Tapa de Asado de Cerdo (x kg)", [r"\btapa\s+de\s+asado\b.*\bcerdo\b|\bcerdo\b.*\btapa\s+de\s+asado\b"]),
    ("colita_cuadril_cerdo", "Colita de Cuadril de Cerdo (x kg)", [r"\bcolita\s+de\s+cuadril\b.*\bcerdo\b|\bcerdo\b.*\bcolita\s+de\s+cuadril\b"]),
    ("matambre_cerdo", "Matambre de Cerdo (x kg)", [r"\bmatambre\b.*\bcerdo\b|\bmatambrito\b|\bcerdo\b.*\bmatambre\b"]),
    ("picada_cerdo", "Carne Picada de Cerdo (x kg)", [r"\b(carne\s+picada|picada)\b.*\bcerdo\b|\bcerdo\b.*\b(carne\s+picada|picada)\b"]),
    ("solomillo_cerdo", "Solomillo de Cerdo (x kg)", [r"\bsolomillo\b|\blomo\b.*\bcerdo\b|\bcerdo\b.*\blomo\b"]),
    ("bondiola", "Bondiola de Cerdo (x kg)", [r"\bbondiola\b"]),
    ("pechito_cerdo", "Pechito de Cerdo (x kg)", [r"\bpechito\s+de\s+cerdo\b|\bpechito\b.*\bcerdo\b|\bpechito\b|\bribs\b.*\bcerdo\b"]),
    ("costillita_cerdo", "Costillitas de Cerdo (x kg)", [r"\b(costillita|costillitas|carre|carré)\s+de\s+cerdo\b|\b(carre|carré)\b.*\bcerdo\b|\bcostillitas?\b.*\bcerdo\b"]),
    ("churrasquito_cerdo", "Churrasquito de Cerdo (x kg)", [r"\bchurrasquito[s]?\b"]),

    # POLLO ESPECÍFICOS
    ("pechuga_pollo", "Pechuga de Pollo / Suprema (x kg)", [r"\b(pechuga|suprema)\b.*\bpollo\b|\bpechuga\b|\bsuprema\b"]),
    ("pata_muslo", "Pata y Muslo de Pollo (x kg)", [r"\bpata\s+y\s+muslo\b|\bcuarto\s+trasero\b"]),
    ("pollo_entero", "Pollo Entero Fresco (x kg)", [r"\bpollo\s+entero\b|\bpollo\s+fresco\b"]),
    ("matambre_pollo", "Matambre de Pollo (x kg)", [r"\bmatambre\b.*\bpollo\b|\bpollo\b.*\bmatambre\b"]),
    ("picada_pollo", "Carne Picada de Pollo (x kg)", [r"\b(carne\s+picada|picada)\b.*\bpollo\b|\bpollo\b.*\b(carne\s+picada|picada)\b"]),

    # VACUNO
    ("vacio_vacuno", "Vacío Vacuno (x kg)", [r"\b(vacio|vac[ií]o)\b(?!.*\b(cerdo|pollo)\b)"]),
    ("entrana_vacuna", "Entraña Vacuna (x kg)", [r"\b(entrana|entraña)\b(?!.*\b(cerdo|pollo)\b)"]),
    ("tapa_asado", "Tapa de Asado (x kg)", [r"\btapa\s+de\s+asado\b(?!.*\b(cerdo|pollo)\b)"]),
    ("asado_tira", "Asado de Tira (x kg)", [r"\basado\b.*\b(tira|centro|banderita|tablita|medio|ventana)\b(?!.*\b(cerdo|pollo)\b)", r"\basado\b(?!.*\b(tapa|americano|cerdo|pollo|locos|sal)\b)"]),
    ("bife_chorizo", "Bife de Chorizo (x kg)", [r"\bbife[s]?\s+de\s+chorizo\b(?!.*\b(cerdo|pollo)\b)"]),
    ("bife_ancho", "Bife Ancho (x kg)", [r"\bbife[s]?\s+ancho[s]?\b(?!.*\b(cerdo|pollo)\b)"]),
    ("bife_angosto", "Bife Angosto (x kg)", [r"\bbife[s]?\s+angosto[s]?\b(?!.*\b(cerdo|pollo)\b)"]),
    ("ojo_bife", "Ojo de Bife (x kg)", [r"\bojo\s+de\s+bife\b(?!.*\b(cerdo|pollo)\b)"]),
    ("lomo", "Lomo Vacuno (x kg)", [r"\blomo\b(?!.*\b(cerdo|pollo|canadiense|bola|atun|atún|praga)\b)"]),
    ("colita_cuadril", "Colita de Cuadril (x kg)", [r"\bcolita\s+de\s+cuadril\b(?!.*\b(cerdo|pollo)\b)"]),
    ("cuadril", "Cuadril (x kg)", [r"\bcuadril\b(?!.*\b(colita|tapa|cerdo|pollo)\b)"]),
    ("matambre_vacuno", "Matambre Vacuno (x kg)", [r"\bmatambre\b(?!.*\b(cerdo|pollo)\b)"]),
    ("peceto", "Peceto (x kg)", [r"\bpeceto\b(?!.*\b(cerdo|pollo)\b)"]),
    ("nalga", "Nalga para Milanesa (x kg)", [r"\bnalga\b(?!.*\b(cerdo|pollo)\b)"]),
    ("bola_lomo", "Bola de Lomo (x kg)", [r"\bbola\s+de\s+lomo\b(?!.*\b(cerdo|pollo)\b)"]),
    ("cuadrada", "Cuadrada para Milanesa (x kg)", [r"\bcuadrada\b(?!.*\b(cerdo|pollo)\b)"]),
    ("picada_especial", "Carne Picada Especial (x kg)", [r"\b(carne\s+picada|picada)\b.*\b(especial|magra|seleccion|primera)\b(?!.*\b(cerdo|pollo)\b)"]),
    ("picada_comun", "Carne Picada Común (x kg)", [r"\bcarne\s+picada\b(?!.*\b(cerdo|pollo)\b)"]),

    # EMBUTIDOS / ACHURAS
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
    clean_nom = re.sub(r"\benv(?:asado)?\s+al\s+vac[ií]o\b", " ", clean_nom)
    clean_nom = re.sub(r"\benv\s+vac[ií]o\b", " ", clean_nom)
    clean_nom = " ".join(clean_nom.split())

    for key, display_name, patterns in _MEAT_TAXONOMY:
        for pat in patterns:
            target = clean_nom if key.startswith("vacio") else nom
            if re.search(pat, target):
                return key, display_name
    return None


def _store_in_memory(flat_products: list[dict]) -> list[dict]:
    """Agrupa en memoria aplicando jerarquía de 4 niveles:
    Nivel 1: GS1 EAN-13 validado (Modulo 10, excluyendo balanza 20-29).
    Nivel 2: Marca y Modelo Canónico Alfanumérico (electro/tech/hogar).
    Nivel 3: Taxonomía de frutas/verduras y cortes de carnicería.
    Nivel 4: Firma canónica de fabricante GS1 (misma marca/volumen/tokens y prefijo compatible).
    Incluye guarda de razón de precios (0.35 <= ratio <= 2.8) y registro de aliases bidireccionales."""
    by_ean: dict[str, dict] = {}
    for d in flat_products:
        if not d:
            continue
        p_venta = _safe_float(d.get("precio_venta"), 0.0)
        stock_val = _safe_int(d.get("stock"), 0)
        if p_venta <= 0 or stock_val <= 0:
            continue

        d_nom = (d.get("nombre") or "").strip()
        d_marca = (d.get("marca") or "").strip()
        d_store = d.get("supermercado") or "Store"
        item_id = str(d.get("itemId") or d.get("sku") or "")

        # Guarda previa: Accesorios y repuestos
        if is_accessory(d_nom):
            clean_toks = re.sub(r'[^A-Z0-9]', '', d_nom.upper())[:30]
            clean_st = re.sub(r'[^A-Z0-9]', '', d_store.upper())
            group_id = f"ACC_{clean_st}_{item_id or clean_toks}"
            is_canonical_fresh = False
            base_model = ""
            model_key = ""
            norm_e = ""
            has_valid_ean = False
        else:
            # Tier 3: Frutas, verduras y carnicería
            prod_match = _match_produce(d)
            meat_match = _match_meat(d) if not prod_match else None
            if prod_match:
                canon_key, display_title = prod_match
                group_id = f"PRODUCE_{canon_key.upper()}"
                d_nom = display_title
                d_marca = "Verdulería"
                is_canonical_fresh = True
                base_model = ""
                model_key = ""
                norm_e = ""
                has_valid_ean = False
            elif meat_match:
                canon_key, display_title = meat_match
                group_id = f"MEAT_{canon_key.upper()}"
                d_nom = display_title
                d_marca = "Carnicería"
                is_canonical_fresh = True
                base_model = ""
                model_key = ""
                norm_e = ""
                has_valid_ean = False
            else:
                is_canonical_fresh = False
                raw_e = str(d.get("raw_ean") or d.get("ean") or "").strip()
                norm_e = normalize_ean(raw_e)
                has_valid_ean = bool(norm_e and is_valid_ean13(norm_e) and not is_internal_scale(norm_e))

                model_key = d.get("model_key") or ""
                base_model = d.get("modelo") or ""
                if not model_key:
                    base_model, model_key = extract_canonical_model({}, {}, d_nom, brand=d_marca)

                # Aliasing bidireccional EAN <-> Modelo
                if has_valid_ean and model_key:
                    _EAN_TO_MODEL[norm_e] = model_key
                    _MODEL_TO_EAN.setdefault(model_key, norm_e)
                    _EAN_ALIASES.setdefault(norm_e, set()).add(model_key)
                    _MODEL_ALIASES.setdefault(model_key, set()).add(norm_e)

                # Resolución jerárquica de clave de grupo
                if model_key:
                    # Tier 2 Priority: unifica comercios con EAN y comercios con solo Modelo
                    group_id = model_key
                elif has_valid_ean:
                    # Tier 1 Priority: resuelve alias de modelo si existe, de lo contrario EAN
                    group_id = _EAN_TO_MODEL.get(norm_e, norm_e)
                elif norm_e and is_internal_scale(norm_e):
                    # Códigos de balanza interna (20-29): aislamiento por tienda
                    group_id = f"{norm_e}_{d_store}"
                elif norm_e:
                    group_id = norm_e
                else:
                    clean_st = re.sub(r'[^A-Z0-9]', '', d_store.upper())
                    group_id = f"ITEM_{clean_st}_{item_id or abs(hash(d_nom)) % 10000000}"

        clean_d_img = _clean_image_url(d.get("imagen"))

        # Coherencia semántica básica
        if not is_canonical_fresh and group_id in by_ean:
            if not _is_semantically_coherent(by_ean[group_id]["nombre"], d_nom):
                group_id = f"{group_id}_{d_store}"

        # Guarda de razón de precios (0.35 <= cand_price / group_price <= 2.8)
        if group_id in by_ean and by_ean[group_id]["offers_by_store"]:
            existing_prices = [
                float(o["precio"]) for o in by_ean[group_id]["offers_by_store"].values()
                if o.get("precio") and float(o["precio"]) > 0
            ]
            if existing_prices:
                avg_p = sum(existing_prices) / len(existing_prices)
                if p_venta < 0.35 * avg_p or p_venta > 2.8 * avg_p:
                    clean_st = re.sub(r'[^A-Z0-9]', '', d_store.upper())
                    group_id = f"{group_id}_OUTLIER_{clean_st}_{item_id or abs(hash(d_nom)) % 10000000}"

        g = by_ean.setdefault(group_id, {
            "id": group_id,
            "ean": group_id,
            "primary_ean": norm_e if (not is_canonical_fresh and has_valid_ean) else "",
            "model_key": model_key if (not is_canonical_fresh and model_key) else "",
            "modelo": base_model if not is_canonical_fresh else "",
            "tipo": d.get("tipo") or "",
            "nombre": d_nom if is_canonical_fresh else (d.get("nombre") or ""),
            "marca": d_marca if is_canonical_fresh else (d_marca if _is_valid_brand(d_marca) else "Genérico"),
            "imagen": clean_d_img,
            "offers_by_store": {},
            "all_names": set(),
        })

        orig_nom = (d.get("nombre") or "").strip()
        if orig_nom:
            g["all_names"].add(orig_nom)
            if not is_canonical_fresh and ("24.7" in orig_nom or "24 7" in orig_nom) and not ("24.7" in g["nombre"] or "24 7" in g["nombre"]):
                g["nombre"] = orig_nom
        if not g["imagen"] and clean_d_img:
            g["imagen"] = clean_d_img
        if not _is_valid_brand(g["marca"]) and _is_valid_brand(d_marca):
            g["marca"] = d_marca
        if not g.get("tipo") and d.get("tipo"):
            g["tipo"] = d.get("tipo")
        if not g.get("modelo") and base_model:
            g["modelo"] = base_model
        if not g.get("primary_ean") and norm_e and has_valid_ean:
            g["primary_ean"] = norm_e

        offer = _to_offer_dict(d)
        if is_canonical_fresh and d_store in g["offers_by_store"]:
            existing = g["offers_by_store"][d_store]
            p_exist = existing.get("unit_price") or existing.get("precio") or float("inf")
            p_new = offer.get("unit_price") or offer.get("precio") or float("inf")
            if p_new < p_exist:
                g["offers_by_store"][d_store] = offer
        else:
            g["offers_by_store"][d_store] = offer

    # Rebalanceo de grupos y blindaje contra usurpación por orden de llegada (Arrival Order Usurpation Guard)
    _ACC_INDICATORS = re.compile(
        r'\b(cargador|cable|funda|case|estuche|vidrio|film|soporte|control remoto|repuesto|bateria|batería|adaptador|auricular|auriculares|correa|malla|tapa|modulo|módulo|display|filtro|bolsa)\b',
        re.IGNORECASE
    )
    _DEVICE_INDICATORS = re.compile(
        r'\b(celular|celulares|telefono|teléfono|smartphone|smart tv|televisor|tv|heladera|heladeras|lavarropas|lavavajillas|aire acondicionado|notebook|notebooks|laptop|laptops|tablet|tablets|microondas|freidora|aspiradora|taladro|cafetera|purificador|afeitadora)\b',
        re.IGNORECASE
    )

    outlier_keys = [k for k in list(by_ean.keys()) if "_OUTLIER_" in k]
    if outlier_keys:
        outliers_by_base: dict[str, list[str]] = {}
        for ok in outlier_keys:
            base_key = ok.split("_OUTLIER_")[0]
            outliers_by_base.setdefault(base_key, []).append(ok)

        def _card_legitimacy_score(g: dict) -> float:
            offers = list(g.get("offers_by_store", {}).values())
            nom = g.get("nombre") or ""
            score = len(offers) * 50.0

            if _ACC_INDICATORS.search(nom) or is_accessory(nom):
                score -= 100.0
            if _DEVICE_INDICATORS.search(nom):
                score += 40.0
            pri_e = g.get("primary_ean") or ""
            if pri_e and len(pri_e) == 13 and is_valid_ean13(pri_e) and not is_internal_scale(pri_e):
                score += 20.0
            return score

        for base_key, related_outliers in outliers_by_base.items():
            if base_key not in by_ean:
                continue
            primary_g = by_ean[base_key]
            primary_score = _card_legitimacy_score(primary_g)

            best_candidate_key = None
            best_candidate_score = -9999.0

            for ok in related_outliers:
                if ok not in by_ean:
                    continue
                cand_g = by_ean[ok]
                cand_score = _card_legitimacy_score(cand_g)
                if cand_score > best_candidate_score:
                    best_candidate_score = cand_score
                    best_candidate_key = ok

            if best_candidate_key and best_candidate_score > primary_score:
                promoted_g = by_ean[best_candidate_key]

                # Demote primary_g a outlier
                st_pri = list(primary_g["offers_by_store"].keys())[0] if primary_g["offers_by_store"] else "UNKNOWN"
                clean_st_pri = re.sub(r'[^A-Z0-9]', '', st_pri.upper())
                pri_id = primary_g.get("primary_ean") or abs(hash(primary_g.get("nombre", ""))) % 10000000
                demoted_key = f"{base_key}_OUTLIER_{clean_st_pri}_{pri_id}"

                primary_g["id"] = demoted_key
                primary_g["ean"] = demoted_key
                by_ean[demoted_key] = primary_g

                # Promote candidate a primary
                promoted_g["id"] = base_key
                promoted_g["ean"] = promoted_g.get("primary_ean") or base_key
                by_ean[base_key] = promoted_g
                del by_ean[best_candidate_key]

                if promoted_g.get("primary_ean"):
                    _MODEL_TO_EAN[base_key] = promoted_g["primary_ean"]

                # Unificar otros outliers compatibles con la nueva tarjeta principal
                p_prom_prices = [
                    float(o["precio"]) for o in promoted_g["offers_by_store"].values()
                    if o.get("precio") and float(o["precio"]) > 0
                ]
                if p_prom_prices:
                    avg_prom = sum(p_prom_prices) / len(p_prom_prices)
                    for other_ok in related_outliers:
                        if other_ok == best_candidate_key or other_ok not in by_ean:
                            continue
                        other_g = by_ean[other_ok]
                        other_prices = [
                            float(o["precio"]) for o in other_g["offers_by_store"].values()
                            if o.get("precio") and float(o["precio"]) > 0
                        ]
                        if not other_prices:
                            continue
                        avg_other = sum(other_prices) / len(other_prices)
                        if 0.35 * avg_prom <= avg_other <= 2.8 * avg_prom:
                            disjoint = set(promoted_g["offers_by_store"].keys()).isdisjoint(other_g["offers_by_store"].keys())
                            if disjoint:
                                for st, off in other_g["offers_by_store"].items():
                                    promoted_g["offers_by_store"][st] = off
                                promoted_g.setdefault("all_names", set()).update(other_g.get("all_names") or [])
                                del by_ean[other_ok]

    # Segunda pasada genérica: fusionar grupos con distinto EAN pero idéntica firma canónica
    # (Misma marca + Mismo peso/volumen + Mismos tokens de producto/variante + Cadenas disjuntas + Mismo prefijo GS1)
    ean_list = sorted(
        by_ean.keys(),
        key=lambda e: (-len(by_ean[e]["offers_by_store"]), e),
    )
    by_sig: dict[tuple, list[str]] = {}
    merged_away: set[str] = set()

    for ean in ean_list:
        if ean.startswith(("PRODUCE_", "MEAT_", "ACC_")):
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
            # 3. Coherencia semántica de categoría y tokens
            if not _is_semantically_coherent(primary_g["nombre"], g["nombre"]):
                continue
            # 4. Coherencia de precios (evitar unir un bulto mal rotulado con una unidad)
            p_main = sum(o["precio"] for o in primary_g["offers_by_store"].values()) / len(primary_g["offers_by_store"])
            p_cand = sum(o["precio"] for o in g["offers_by_store"].values()) / len(g["offers_by_store"])
            if not (0.35 <= (p_cand / p_main) <= 2.8):
                continue

            # Fusionar ofertas dentro del grupo principal
            for st, off in g["offers_by_store"].items():
                primary_g["offers_by_store"][st] = off
            primary_g.setdefault("all_names", set()).update(g.get("all_names") or [])
            if not primary_g["imagen"] and g["imagen"]:
                primary_g["imagen"] = g["imagen"]
            _EAN_ALIASES.setdefault(primary_ean, set()).add(ean)
            _EAN_ALIASES.setdefault(ean, set()).add(primary_ean)
            merged_away.add(ean)
            merged = True
            break

        if not merged:
            by_sig.setdefault(sig, []).append(ean)

    groups: list[dict] = []
    for group_id, g in by_ean.items():
        if group_id in merged_away:
            continue
        cant, u_tit = extraer_unidad_titulo(g["nombre"])
        offers = list(g["offers_by_store"].values())
        if not group_id.startswith(("PRODUCE_", "MEAT_", "ACC_")):
            for o in offers:
                eff_p = (
                    float(o["precio"])
                    if o.get("requires_club")
                    else float(o.get("promo_unit_price") or o["precio"])
                )
                if cant > 0:
                    p_u, u_norm = normalizar_unidad(eff_p / cant, u_tit)
                    o["unit_price"] = sanity_precio_unidad(eff_p, p_u, u_norm)
                    o["unit_measure"] = u_norm

        gallery_images = _build_gallery_images(offers, g.get("imagen") or "")
        primary_img = gallery_images[0] if gallery_images else _clean_image_url(g.get("imagen"))
        g["imagen"] = primary_img

        g_dict = {
            "id": group_id,
            "ean": g.get("primary_ean") or group_id,
            "primary_ean": g.get("primary_ean") or "",
            "model_key": g.get("model_key") or "",
            "nombre": g["nombre"],
            "marca": g["marca"],
            "modelo": g.get("modelo") or "",
            "tipo": g.get("tipo") or "",
            "vertical": g.get("tipo") or (offers[0].get("store_type") if offers else "supermarket"),
            "best_offer": offers[0] if offers else None,
            "imagen": primary_img,
            "gallery_images": gallery_images,
            "offers": offers,
            "all_names": list(g.get("all_names") or []),
        }

        # Persistir en memoria para el optimizador Smart Cart
        prod_mem = {
            "id": group_id,
            "ean": g_dict["ean"],
            "nombre": g["nombre"],
            "marca": g["marca"],
            "modelo": g.get("modelo") or "",
            "tipo": g.get("tipo") or "",
            "imagen": primary_img,
            "gallery_images": gallery_images,
        }
        _LIVE_PRODUCTS_MEM[group_id] = prod_mem
        _LIVE_PRODUCTS_MEM[group_id.lower()] = prod_mem
        mem_offers = _LIVE_OFFERS_MEM.setdefault(group_id, {})
        for st, off in g["offers_by_store"].items():
            mem_offers[st] = {**off, "ean": g_dict["ean"], "nombre": g["nombre"]}
        _LIVE_OFFERS_MEM[group_id.lower()] = mem_offers

        pri_ean = g.get("primary_ean")
        if pri_ean and pri_ean != group_id:
            _LIVE_PRODUCTS_MEM[pri_ean] = prod_mem
            _LIVE_PRODUCTS_MEM[pri_ean.lower()] = prod_mem
            _LIVE_OFFERS_MEM[pri_ean] = mem_offers
            _LIVE_OFFERS_MEM[pri_ean.lower()] = mem_offers

        m_key = g.get("model_key")
        if m_key and m_key != group_id:
            _LIVE_PRODUCTS_MEM[m_key] = prod_mem
            _LIVE_PRODUCTS_MEM[m_key.lower()] = prod_mem
            _LIVE_OFFERS_MEM[m_key] = mem_offers
            _LIVE_OFFERS_MEM[m_key.lower()] = mem_offers

        all_aliases = (
            _MODEL_ALIASES.get(group_id, set())
            | _EAN_ALIASES.get(group_id, set())
            | (_EAN_ALIASES.get(pri_ean, set()) if pri_ean else set())
            | (_MODEL_ALIASES.get(m_key, set()) if m_key else set())
        )
        for al in all_aliases:
            if al:
                _LIVE_PRODUCTS_MEM[al] = prod_mem
                _LIVE_PRODUCTS_MEM[al.lower()] = prod_mem
                _LIVE_OFFERS_MEM[al] = mem_offers
                _LIVE_OFFERS_MEM[al.lower()] = mem_offers

        if group_id.startswith(("MEAT_", "PRODUCE_")):
            if "CHORIZO" in group_id:
                _LIVE_OFFERS_MEM["MEAT_CHORIZO"] = mem_offers
                _LIVE_OFFERS_MEM["meat_chorizo"] = mem_offers
                _LIVE_PRODUCTS_MEM["MEAT_CHORIZO"] = prod_mem
                _LIVE_PRODUCTS_MEM["meat_chorizo"] = prod_mem
            if "ASADO_TIRA" in group_id:
                _LIVE_OFFERS_MEM["MEAT_ASADO"] = mem_offers
                _LIVE_OFFERS_MEM["meat_asado"] = mem_offers
            if "VACIO_VACUNO" in group_id:
                _LIVE_OFFERS_MEM["MEAT_VACIO"] = mem_offers
                _LIVE_OFFERS_MEM["meat_vacio"] = mem_offers
                _LIVE_PRODUCTS_MEM["MEAT_VACIO"] = prod_mem
                _LIVE_PRODUCTS_MEM["meat_vacio"] = prod_mem
            if "ENTRANA_VACUNA" in group_id:
                _LIVE_OFFERS_MEM["MEAT_ENTRANA"] = mem_offers
                _LIVE_OFFERS_MEM["meat_entrana"] = mem_offers
                _LIVE_PRODUCTS_MEM["MEAT_ENTRANA"] = prod_mem
                _LIVE_PRODUCTS_MEM["meat_entrana"] = prod_mem
            if "MATAMBRE_VACUNO" in group_id:
                _LIVE_OFFERS_MEM["MEAT_MATAMBRE"] = mem_offers
                _LIVE_OFFERS_MEM["meat_matambre"] = mem_offers
                _LIVE_PRODUCTS_MEM["MEAT_MATAMBRE"] = prod_mem
                _LIVE_PRODUCTS_MEM["meat_matambre"] = prod_mem

        groups.append(g_dict)

    # Prioritize genuine commercial products over quarantined accessories
    groups.sort(key=lambda grp: (
        1 if (grp.get("id", "").startswith("ACC_") or is_accessory(grp.get("nombre", ""))) else 0,
        -len(grp.get("offers", [])),
    ))
    return groups


STORE_TIMEOUTS: dict[str, float] = {
    "Coto": 4.5,
    "MercadoLibre": 4.5,
    "Provincia Compras": 4.0,
    "On City": 4.0,
    "Fravega": 3.8,
}
DEFAULT_STORE_TIMEOUT = 3.5


async def _fetch_store_safe(
    coroutine,
    store_name: str,
    timeout: float | None = None,
) -> list[dict]:
    """Ejecuta la consulta a una tienda con timeout aislado y protección de excepciones.
    Garantiza que una tienda lenta o caída nunca bloquee o aborte la búsqueda global.
    """
    effective_timeout = timeout or STORE_TIMEOUTS.get(store_name, DEFAULT_STORE_TIMEOUT)
    try:
        res = await asyncio.wait_for(coroutine, timeout=effective_timeout)
        if isinstance(res, list):
            return res
        return []
    except asyncio.TimeoutError:
        return []
    except Exception:
        return []


async def _fetch_all_live_async(
    client: httpx.AsyncClient,
    query: str,
    limit_per_store: int = 16,
    order_by: str = "OrderByTopSaleDESC",
    region_map: dict[str, str | None] | None = None,
    vertical: str | None = None,
    store_type: str | None = None,
    grocery_only: bool = False,
    cp: str | None = None,
) -> tuple[list[dict], dict[str, int], dict[str, set[str]], list[str]]:
    """Consulta concurrentemente todas las tiendas activas mediante asyncio.gather.
    Aplica filtros verticales, timeouts individuales y aislamiento de errores.

    Retorna:
        - flat_products: lista unificada de ofertas obtenidas.
        - by_store: conteo de productos por tienda.
        - store_eans: conjunto de EANs encontrados por tienda.
        - ean_priority: lista ordenada de EANs para Etapa 2.
    """
    region_map = region_map or {}
    q_clean = query.strip()
    is_ean = q_clean.isdigit() and 8 <= len(q_clean) <= 14

    # Determinar tiendas VTEX según vertical
    target_v = set()
    if vertical and vertical.strip().lower() not in ("todos", "all", ""):
        target_v.update(v.strip().lower() for v in vertical.split(",") if v.strip() and v.strip().lower() not in ("todos", "all"))
    if store_type and store_type.strip().lower() not in ("todos", "all", ""):
        target_v.update(st.strip().lower() for st in store_type.split(",") if st.strip() and st.strip().lower() not in ("todos", "all"))

    vtex_candidates = list(LIVE_VTEX_DOMAINS.keys())
    if target_v:
        vtex_candidates = [
            st for st in vtex_candidates
            if store_vertical(st).lower() in target_v
            or ("marketplace" in target_v and is_marketplace(st))
            or (("supermarket" in target_v or "pharmacy" in target_v) and st in ("Farmacity", "Simplicity", "Farmaonline", "Farmaplus"))
        ]

    # Excluir alias duplicados para evitar llamadas dobles al mismo backend
    alias_keys = {
        "ProvinciaCompras", "OnCity", "Frávega", "Moulinex / Tefal", "Moulinex/Tefal",
        "Sony Store", "SonyStore", "Perfumerías Pigmento", "Perfumerias Pigmento",
        "Toledo Digital", "ToledoDigital", "Food Market", "BodegasBianchi",
    }
    vtex_names = [
        st for st in vtex_candidates
        if st not in alias_keys and region_map.get(st) != "__NO_DELIVERY__"
    ]

    tasks = []
    task_stores = []

    # A. Tiendas VTEX
    for st in vtex_names:
        st_vert = store_vertical(st)
        if is_ean:
            coro = fetch_vtex_by_eans_live(
                client, st, [q_clean], region_id=region_map.get(st),
                grocery_only=grocery_only, store_type=st_vert,
            )
        else:
            coro = fetch_vtex_store_live(
                client, st, q_clean, limit=limit_per_store, order_by=order_by,
                region_id=region_map.get(st), grocery_only=grocery_only, store_type=st_vert,
            )
        tasks.append(_fetch_store_safe(coro, store_name=st))
        task_stores.append(st)

    # B. Coto Digital
    if not target_v or "supermarket" in target_v:
        tasks.append(_fetch_store_safe(fetch_coto_live(client, q_clean, limit=limit_per_store, grocery_only=grocery_only), store_name="Coto"))
        task_stores.append("Coto")

    # C. Shopify Stores (LaBarraCCU, Bodegas Bianchi)
    if not target_v or any(v in target_v for v in ("supermarket", "specialty")):
        for sh_st in SHOPIFY_DOMAINS.keys():
            if sh_st in alias_keys:
                continue
            tasks.append(_fetch_store_safe(fetch_shopify_live(client, sh_st, q_clean, limit=10), store_name=sh_st))
            task_stores.append(sh_st)

    # D. Tiendanube Stores (LaBarata, TonelPrivado, DePastura)
    if not target_v or any(v in target_v for v in ("supermarket", "specialty")):
        for tn_st in TIENDANUBE_DOMAINS.keys():
            tasks.append(_fetch_store_safe(fetch_tiendanube_live(client, tn_st, q_clean, limit=10), store_name=tn_st))
            task_stores.append(tn_st)

    # E. WooCommerce Stores (Arcor en Casa)
    if not target_v or "supermarket" in target_v:
        for wc_st in WOOCOMMERCE_DOMAINS.keys():
            tasks.append(_fetch_store_safe(fetch_woocommerce_live(client, wc_st, q_clean, limit=10), store_name=wc_st))
            task_stores.append(wc_st)

    # F. Mercado Libre
    if not target_v or any(v in target_v for v in ("marketplace", "electro", "supermarket", "specialty")):
        tasks.append(_fetch_store_safe(fetch_mercadolibre_live(client, q_clean, limit=14, cp=cp), store_name="MercadoLibre"))
        task_stores.append("MercadoLibre")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    flat_products: list[dict] = []
    by_store: dict[str, int] = {st: 0 for st in task_stores}
    store_eans: dict[str, set[str]] = {st: set() for st in task_stores}
    ean_priority: list[str] = []

    for st_name, res in zip(task_stores, results):
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

    return flat_products, by_store, store_eans, ean_priority


async def live_search_and_sync(
    query: str,
    limit_per_store: int = 16,
    only_offers: bool = False,
    cp: str | None = None,
    force: bool = False,
    vertical: str | None = None,
    store_type: str | None = None,
    grocery_only: bool = False,
) -> dict:
    """Ejecuta la búsqueda 100% en vivo en los motores (VTEX + Coto + Shopify + Tiendanube + MeLi)
    con ejecución concurrente protegida, aislando timeouts y errores de cada tienda.
    """
    q_norm = " ".join(query.lower().strip().split())
    if not q_norm:
        q_norm = "leche"

    target_v = set()
    if vertical and vertical.strip().lower() not in ("todos", "all", ""):
        target_v.update(v.strip().lower() for v in vertical.split(",") if v.strip() and v.strip().lower() not in ("todos", "all"))
    if store_type and store_type.strip().lower() not in ("todos", "all", ""):
        target_v.update(st.strip().lower() for st in store_type.split(",") if st.strip() and st.strip().lower() not in ("todos", "all"))

    cache_key = f"{q_norm}|{'offers' if only_offers else 'all'}|{cp or ''}|{vertical or 'all'}|{store_type or 'all'}|{grocery_only}"
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

    limits = httpx.Limits(max_connections=150, max_keepalive_connections=50, keepalive_expiry=30.0)
    timeout = httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=5.0)

    async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=True) as client:
        # Etapa 1: Consulta concurrente con _fetch_all_live_async
        flat_products, by_store, store_eans, ean_priority = await _fetch_all_live_async(
            client=client,
            query=q_norm,
            limit_per_store=limit_per_store,
            order_by=order_by,
            region_map=region_map,
            vertical=vertical,
            store_type=store_type,
            grocery_only=grocery_only,
            cp=cp,
        )

        # Etapa 2: Completado cruzado por EAN en VTEX
        vtex_only_prods = [p for p in flat_products if p.get("supermercado") != "Coto"]
        corrected_q = _detect_corrected_query(q_norm, vtex_only_prods)

        top_eans = ean_priority[:22]
        ean_tasks = []
        ean_task_stores = []
        if top_eans and not q_norm.isdigit():
            target_cross_chains = (
                [st for st in SUPERMARKET_CHAINS if not target_v or "supermarket" in target_v]
                if target_v and "supermarket" in target_v and not any(v in target_v for v in ("electro", "marketplace"))
                else (
                    [st for st in ELECTRO_MARKETPLACE_CHAINS if not target_v or any(v in target_v for v in ("electro", "marketplace"))]
                    if target_v and any(v in target_v for v in ("electro", "marketplace")) and "supermarket" not in target_v
                    else SUPERMARKET_CHAINS + ("Fravega", "Cetrogar", "Provincia Compras", "On City")
                )
            )
            for st in target_cross_chains:
                if st not in LIVE_VTEX_DOMAINS or region_map.get(st) == "__NO_DELIVERY__":
                    continue
                missing = [e for e in top_eans if e not in store_eans.get(st, set())]
                if missing:
                    coro = fetch_vtex_by_eans_live(
                        client, st, missing[:20], region_id=region_map.get(st),
                        grocery_only=grocery_only, store_type=store_vertical(st),
                    )
                    ean_tasks.append(_fetch_store_safe(coro, store_name=st, timeout=3.0))
                    ean_task_stores.append(st)

            # Completado cruzado por EAN en Mercado Libre para los ítems principales
            if not target_v or any(v in target_v for v in ("marketplace", "electro", "supermarket")):
                missing_meli = [e for e in top_eans[:10] if e not in store_eans.get("MercadoLibre", set())]
                for me in missing_meli:
                    ean_tasks.append(_fetch_store_safe(fetch_mercadolibre_live(client, me, limit=1, cp=cp), store_name="MercadoLibre", timeout=2.5))
                    ean_task_stores.append("MercadoLibre")

        if corrected_q and corrected_q != q_norm and (not target_v or "supermarket" in target_v):
            ean_tasks.append(_fetch_store_safe(fetch_coto_live(client, corrected_q, limit=limit_per_store, grocery_only=grocery_only), store_name="Coto", timeout=3.5))
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
    vertical: str | None = None,
    store_type: str | None = None,
    grocery_only: bool = False,
) -> list[dict]:
    """Devuelve los grupos de productos 100% desde la búsqueda en vivo (sin base de datos),
    filtrando falsos positivos de subcadena (ej. 'Pepsina' al buscar 'Pepsi') y ordenando
    de arriba hacia abajo por el precio por litro/kilo/unidad más conveniente.
    """
    q_clean = query.strip()
    effective_q = q_clean if len(q_clean) >= 2 else "coca cola leche"
    res = await live_search_and_sync(
        effective_q,
        limit_per_store=18,
        only_offers=only_offers,
        cp=cp,
        vertical=vertical,
        store_type=store_type,
        grocery_only=grocery_only,
    )
    raw_groups = []
    for g in res.get("groups", []):
        coherent_offers = [
            o for o in g.get("offers", [])
            if _is_semantically_coherent(g.get("nombre") or "", o.get("nombre") or g.get("nombre") or "")
        ]
        if not coherent_offers:
            continue
        gallery = _build_gallery_images(coherent_offers, g.get("imagen") or "")
        raw_groups.append({
            **g,
            "imagen": gallery[0] if gallery else _clean_image_url(g.get("imagen")),
            "gallery_images": gallery,
            "offers": coherent_offers,
            "best_offer": coherent_offers[0] if coherent_offers else None,
        })

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
            all_text = f"{g.get('nombre', '')} {g.get('marca', '')} " + " ".join(g.get("all_names") or [])
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
                all_text = f"{g.get('nombre', '')} {g.get('marca', '')} " + " ".join(g.get("all_names") or [])
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

    # 2. In-memory vertical and store_type filtering
    target_v = set()
    if vertical and vertical.strip().lower() not in ("todos", "all", ""):
        target_v.update(v.strip().lower() for v in vertical.split(",") if v.strip() and v.strip().lower() not in ("todos", "all"))
    if store_type and store_type.strip().lower() not in ("todos", "all", ""):
        target_v.update(st.strip().lower() for st in store_type.split(",") if st.strip() and st.strip().lower() not in ("todos", "all"))

    if target_v:
        filtered_v = []
        for g in groups:
            g_tipo = (g.get("tipo") or "").lower()
            g_vert = (g.get("vertical") or "").lower()
            matching_offers = [
                o for o in g.get("offers", [])
                if (o.get("store_type") or "").lower() in target_v
                or (o.get("tipo") or "").lower() in target_v
                or (store_vertical(o.get("supermercado", "")).lower() in target_v)
            ]
            if matching_offers:
                g_mod = dict(g)
                g_mod["offers"] = matching_offers
                g_mod["best_offer"] = matching_offers[0]
                filtered_v.append(g_mod)
            elif g_tipo in target_v or g_vert in target_v:
                filtered_v.append(g)
        groups = filtered_v

    # 3. In-memory grocery_only filtering
    if grocery_only:
        grocery_filtered = []
        for g in groups:
            g_tipo = (g.get("tipo") or "").lower()
            if g_tipo in ("electro", "hogar", "tecnologia", "ferreteria"):
                continue
            valid_offers = [
                o for o in g.get("offers", [])
                if (o.get("store_type") or "").lower() not in ("electro", "marketplace")
                and (o.get("tipo") or "").lower() not in ("electro", "hogar", "tecnologia", "ferreteria")
            ]
            if valid_offers:
                g_mod = dict(g)
                g_mod["offers"] = valid_offers
                g_mod["best_offer"] = valid_offers[0]
                grocery_filtered.append(g_mod)
        groups = grocery_filtered

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
        g["best_offer"] = g["offers"][0] if g["offers"] else None

    def _group_sort_key(g: dict):
        name_tokens = [_singularize_token(t) for t in _norm_text(g.get("nombre", "")).split()]
        brand_tokens = {_singularize_token(t) for t in _norm_text(g.get("marca", "")).split()}

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
    "MEAT_VACIO": "MEAT_VACIO_VACUNO",
    "MEAT_ENTRANA": "MEAT_ENTRANA_VACUNA",
    "MEAT_MATAMBRE": "MEAT_MATAMBRE_VACUNO",
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
        if e in _EAN_TO_MODEL and _EAN_TO_MODEL[e] in _LIVE_OFFERS_MEM:
            return _LIVE_OFFERS_MEM[_EAN_TO_MODEL[e]]
        if eu in _EAN_TO_MODEL and _EAN_TO_MODEL[eu] in _LIVE_OFFERS_MEM:
            return _LIVE_OFFERS_MEM[_EAN_TO_MODEL[eu]]
        if e in _MODEL_TO_EAN and _MODEL_TO_EAN[e] in _LIVE_OFFERS_MEM:
            return _LIVE_OFFERS_MEM[_MODEL_TO_EAN[e]]
        if eu in _MODEL_TO_EAN and _MODEL_TO_EAN[eu] in _LIVE_OFFERS_MEM:
            return _LIVE_OFFERS_MEM[_MODEL_TO_EAN[eu]]
        aliases = (
            _EAN_ALIASES.get(e, set())
            | _EAN_ALIASES.get(eu, set())
            | _MODEL_ALIASES.get(e, set())
            | _MODEL_ALIASES.get(eu, set())
        )
        for al in aliases:
            if al in _LIVE_OFFERS_MEM:
                return _LIVE_OFFERS_MEM[al]
            if al.upper() in _LIVE_OFFERS_MEM:
                return _LIVE_OFFERS_MEM[al.upper()]
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
                cand_nom = list(offs.values())[0].get("nombre") or ""
                if not _is_semantically_coherent(names_hint[e], cand_nom):
                    continue
                s_nom = _norm_text(cand_nom)
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
            hint_name = names_hint.get(ean) or names.get(ean) or ""
            raw_offs = list(store_map.values())
            if hint_name:
                raw_offs = [
                    o for o in raw_offs
                    if _is_semantically_coherent(hint_name, o.get("nombre") or hint_name)
                ]
            out[ean] = raw_offs
            if ean not in names and out[ean]:
                names[ean] = out[ean][0].get("nombre") or ean
        if ean not in names and names_hint.get(ean):
            names[ean] = names_hint[ean]
    return out, names


async def live_lookup_eans(eans: list[str], cp: str | None = None) -> dict:
    clean_eans = [str(e).strip() for e in eans if str(e).strip().isdigit()][:25]
    if not clean_eans:
        return {"eans": [], "synced": 0, "stores": {}}

    alias_keys = {
        "ProvinciaCompras", "OnCity", "Frávega", "Moulinex / Tefal", "Moulinex/Tefal",
        "Sony Store", "SonyStore", "Perfumerías Pigmento", "Perfumerias Pigmento",
        "Toledo Digital", "ToledoDigital", "Food Market", "BodegasBianchi",
    }
    vtex_names = [st for st in LIVE_VTEX_DOMAINS.keys() if st not in alias_keys]

    async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
        tasks = [
            _fetch_store_safe(fetch_vtex_by_eans_live(client, st, clean_eans), store_name=st, timeout=4.5)
            for st in vtex_names
        ]
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
