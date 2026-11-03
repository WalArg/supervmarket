"""Parsers puros (sin dependencias externas como aiohttp) para VTEX, Coto Endeca y normalización de unidades.
Diseñado para correr dentro de la Serverless Function de Vercel (`api/index.py`).
"""
import re
import json
import unicodedata
from typing import Optional
from datetime import datetime, timezone

CATEGORY_MAPPING = {
    "Almacén": "Supermercado", "Bebidas": "Supermercado", "Frescos": "Supermercado",
    "Limpieza": "Supermercado", "Congelados": "Supermercado", "Alimentos": "Supermercado",
    "Lácteos": "Supermercado", "Desayuno y merienda": "Supermercado",
    "Frutas y Verduras": "Supermercado", "Frutas y verduras": "Supermercado",
    "Carnes": "Supermercado", "Snacks": "Supermercado", "Panadería": "Supermercado",
    "Quesos y Fiambres": "Supermercado", "Pastas": "Supermercado",
    "Perfumería": "Salud y Belleza", "Cuidado Personal": "Salud y Belleza",
    "Farmacia": "Salud y Belleza", "Dermocosmética": "Salud y Belleza",
    "Maquillaje": "Salud y Belleza", "Bebés": "Bebés y Niños", "Mascotas": "Mascotas",
}

COUNTABLE_ITEM_KEYWORDS = (
    "jabon en barra", "jabon de tocador", "jabon tocador", "jabon corporal", "jabon en pan",
    "panal", "panales", "toallitas", "toalla femenina", "toallas femeninas", "protectores diarios",
    "tampon", "tampones", "papel higienico", "rollo de cocina", "rollos de cocina", "servilleta",
    "panuelo", "panuelos", "saquito", "saquitos", "capsula", "capsulas", "comprimido",
    "comprimidos", "pastilla", "pastillas", "preservativo", "preservativos", "afeitadora",
    "cartucho", "repuesto filo", "cepillo", "esponja", "bolsa de residuo", "bolsas de residuo",
    "huevo", "huevos", "vela", "velas", "pila", "pilas", "lampara",
)

MULTIPACK_REGEX = re.compile(
    r'(\d+)\s*(?:botellas?|latas?|unidades?|un|u|paquetes?|packs?)?\s*[xX×]\s*(\d+(?:[.,]\d+)?)\s*'
    r'(l|lt|lts|litro|litros|ml|cc|cm3|g|gr|grs|gramo|gramos|grm|kg|kgs|kilogramo|un|u|unid|unidades|m|mts|metros)\b',
    re.IGNORECASE,
)

MULTIPACK_REV_REGEX = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*'
    r'(l|lt|lts|litro|litros|ml|cc|cm3|g|gr|grs|gramo|gramos|grm|kg|kgs|kilogramo)\s*\.?\s*'
    r'(?:caja|pack|paq|display|bolsa|fardo)?\s*'
    r'(?:[xX×]|de)\s*(\d+)\s*(?:un|u|uni|unid|unidades|botellas?|latas?|pack|paq)?\b',
    re.IGNORECASE,
)

EXPLICIT_UNITS_REGEX = re.compile(
    r'(?:[xX×]\s*(\d+)\s*(?:un|u|ud|uds|uni|unid|unidades)\b)|'
    r'(?:\b(\d+)\s*(?:un|u|ud|uds|uni|unid|unidades|rollos?|paños?|saquitos?|capsulas?|cápsulas?|tiras?|pañales?|comp|comprimidos?)\b)',
    re.IGNORECASE,
)

UNIT_REGEX = re.compile(
    r'(\d+(?:[.,]\d+)?|\d+/\d+)\s*'
    r'(l|lt|lts|litro|litros|ml|cc|cm3|g|gr|grs|gramo|gramos|grm|kg|kgs|kilogramo|kilo|'
    r'un|u|ud|uds|uni|unid|unidades|rollos?|paños?|saquitos?|capsulas?|cápsulas?|tiras?|pañales?|comp|comprimidos?)\b',
    re.IGNORECASE,
)

CLUB_KEYWORDS = (
    "club dia", "mi carrefour", "tarjeta carrefour", "cencopay", "cencosud",
    "mas club", "más club", "tu farmacity", "comunidad", "bsf", "banco",
    "anses", "jubilado", "modo", "bna", "cuenta dni", "mp ", "mercadopago",
)

NON_GROCERY_MARKETPLACE_KEYWORDS = (
    "aspiradora",
    "soporte fijo",
    "soporte tv",
    "soporte movil",
    "colchon",
    "sommier",
    "auriculares",
    "camara hibrida",
    "pesas rusas",
    "kettlebell",
    "soga de salto",
    "powerband",
    "engrampadora",
    "basurero con pedal",
    "limpiafondo",
    "espatula la planchetta",
    "planchetta",
    "smart tv",
    "aire acondicionado",
    "heladera",
    "lavarropas",
    "microondas",
    "freidora de aire",
    "notebook",
    "impresora",
    "bicicleta",
    "mancuerna",
    "colchoneta",
    "taladro",
    "amoladora",
    "hidrolavadora",
    "neumatico",
    "cubierta auto",
)

NON_GROCERY_CATEGORY_KEYWORDS = (
    "electro y tecnologia",
    "electrodomesticos",
    "audio y video",
    "tv y video",
    "informatica",
    "celulares",
    "climatizacion",
    "colchones y sommiers",
    "muebles",
    "deportes y fitness",
    "automotor",
    "ferreteria",
    "herramientas",
    "rodados",
    "jugueteria",
    "tiempo libre",
)


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


# ---------------------------------------------------------------------------
# Robust Numeric & Store Resolution Helpers
# ---------------------------------------------------------------------------

def _safe_int(val, default: int = 0) -> int:
    """Safely converts val to int, handling float strings ('10.0'), None, and type errors."""
    try:
        if val is None or val == "":
            return default
        return int(float(val))
    except (ValueError, TypeError, OverflowError):
        return default


def _safe_float(val, default: float = 0.0) -> float:
    """Safely converts val to float, returning default on ValueError/TypeError."""
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (ValueError, TypeError, OverflowError):
        return default


def _resolve_store_domain(store_name: str) -> str:
    """Safely resolves base store domain from StoreMeta or a sanitized slug fallback."""
    if not store_name:
        return ""
    try:
        from .stores import get_store_meta
        meta = get_store_meta(store_name)
        if meta and meta.get("dominio"):
            return str(meta["dominio"]).rstrip("/")
    except Exception:
        try:
            from stores import get_store_meta
            meta = get_store_meta(store_name)
            if meta and meta.get("dominio"):
                return str(meta["dominio"]).rstrip("/")
        except Exception:
            pass

    slug = re.sub(r"[^a-z0-9]", "", store_name.lower())
    return f"https://www.{slug}.com.ar"


try:
    from .normalization import (
        extract_canonical_model,
        extract_model,
        classify_product_type,
        is_accessory,
        canonical_model_key,
    )
except ImportError:
    from normalization import (
        extract_canonical_model,
        extract_model,
        classify_product_type,
        is_accessory,
        canonical_model_key,
    )


def normalizar_categoria(cat: str) -> str:
    if not cat:
        return "Otros"
    first = cat.split(",")[0].strip().strip("/").split("/")[0].strip()
    return CATEGORY_MAPPING.get(first, first or "Otros")


def normalizar_unidad(precio, unidad):
    if not unidad or not precio:
        return precio, unidad or "un"
    u = str(unidad).lower().strip().rstrip(".")
    p = float(precio)
    if u in ("lt", "lts", "litro", "litros"):
        u = "l"
    elif u in ("gr", "grs", "gramo", "gramos", "grm"):
        u = "g"
    elif u in ("kilogramo", "kilogramos", "kilo", "kgs"):
        u = "kg"
    elif u in ("cc", "cm3", "ml"):
        u = "ml"
    elif u in ("u", "ud", "uds", "uni", "unid", "unidades", "rollo", "rollos", "saquito", "saquitos",
               "capsula", "capsulas", "cápsula", "cápsulas", "tira", "tiras", "pañal", "pañales",
               "comp", "comprimido", "comprimidos"):
        u = "un"

    if u == "ml":
        return round(p * 1000, 2), "l"
    if u == "g":
        return round(p * 1000, 2), "kg"
    return round(p, 2), u


def extraer_unidad_titulo(titulo: str):
    if not titulo:
        return 1.0, "un"

    norm_title = _strip_accents(titulo)
    is_countable = any(k in norm_title for k in COUNTABLE_ITEM_KEYWORDS)

    mp = MULTIPACK_REGEX.search(titulo)
    if mp:
        try:
            mult = float(mp.group(1))
            val = float(mp.group(2).replace(",", "."))
            unidad = mp.group(3).lower()
            if is_countable and 1 <= mult <= 100:
                return mult, "un"
            total = mult * val
            if unidad in ("l", "lt", "lts", "litro", "litros"):
                return total, "l"
            if unidad in ("ml", "cc", "cm3"):
                return total / 1000.0, "l"
            if unidad in ("kg", "kgs", "kilogramo"):
                return total, "kg"
            if unidad in ("g", "gr", "grs", "gramo", "gramos", "grm"):
                return total / 1000.0, "kg"
            if unidad in ("m", "mts", "metros"):
                return mult, "un"
            return total, "un"
        except Exception:
            pass

    mp_rev = MULTIPACK_REV_REGEX.search(titulo)
    if mp_rev:
        try:
            val = float(mp_rev.group(1).replace(",", "."))
            unidad = mp_rev.group(2).lower()
            mult = float(mp_rev.group(3))
            if is_countable and 1 <= mult <= 100:
                return mult, "un"
            total = mult * val
            if unidad in ("l", "lt", "lts", "litro", "litros"):
                return total, "l"
            if unidad in ("ml", "cc", "cm3"):
                return total / 1000.0, "l"
            if unidad in ("kg", "kgs", "kilogramo"):
                return total, "kg"
            if unidad in ("g", "gr", "grs", "gramo", "gramos", "grm"):
                return total / 1000.0, "kg"
        except Exception:
            pass

    if is_countable:
        m_u = EXPLICIT_UNITS_REGEX.search(titulo)
        if m_u:
            try:
                qty_u = float(m_u.group(1) or m_u.group(2))
                if 1 <= qty_u <= 300:
                    return qty_u, "un"
            except Exception:
                pass
        return 1.0, "un"

    if re.search(r'\bx\s*kg\b|\bpor\s*kg\b', titulo, re.IGNORECASE):
        return 1.0, "kg"

    m = UNIT_REGEX.search(titulo)
    if not m:
        return 1.0, "un"
    cant_str = m.group(1).replace(",", ".")
    unidad = m.group(2).lower()
    try:
        if "/" in cant_str:
            num, den = cant_str.split("/")
            cantidad = float(num) / float(den)
        else:
            cantidad = float(cant_str)
        if cantidad <= 0:
            return 1.0, "un"
        if unidad in ("l", "lt", "lts", "litro", "litros"):
            return cantidad, "l"
        if unidad in ("ml", "cc", "cm3"):
            return cantidad / 1000.0, "l"
        if unidad in ("kg", "kgs", "kilogramo", "kilo"):
            return cantidad, "kg"
        if unidad in ("g", "gr", "grs", "gramo", "gramos", "grm"):
            return cantidad / 1000.0, "kg"
        return cantidad, "un"
    except Exception:
        pass
    return 1.0, "un"


def sanity_precio_unidad(precio_total: float, precio_unidad: float, unidad: str):
    if unidad not in ("kg", "l") or not precio_unidad or not precio_total:
        return round(precio_unidad, 2) if precio_unidad else precio_total
    if precio_unidad < precio_total / 100:
        return round(precio_unidad * 1000, 2)
    return round(precio_unidad, 2)


def _has_bin_restriction(teaser: dict) -> bool:
    conds = (
        teaser.get("Conditions")
        or teaser.get("conditions")
        or teaser.get("<Conditions>k__BackingField")
        or {}
    )
    params = (
        conds.get("Parameters")
        or conds.get("parameters")
        or conds.get("<Parameters>k__BackingField")
        or []
    )
    for p in params:
        p_name = str(p.get("Name") or p.get("name") or p.get("<Name>k__BackingField") or "")
        p_val = p.get("Value") or p.get("value") or p.get("<Value>k__BackingField")
        if "RestrictionsBins" in p_name and p_val:
            return True
    return False


def _parse_active_teaser(text: str, base_price: float, list_price: float,
                         force_club: bool = False) -> Optional[dict]:
    if not text:
        return None
    clean = text.strip()
    low = clean.lower()
    is_club = force_club or any(k in low for k in CLUB_KEYWORDS)

    # Las promociones por volumen (2do al X%, NxM) en los supermercados se calculan
    # sobre el precio de lista regular (list_price), NUNCA sobre un precio de oferta ya rebajado (base_price).
    # Si base_price < list_price, la promo por volumen sólo aplica si el precio unitario resultante
    # desde list_price es estrictamente menor que el precio de oferta directa base_price.
    ref_price = list_price if list_price and list_price > 0 else base_price

    m_2do = re.search(
        r"(?:2d[oa](?:\s+unidad)?\s+al\s*(\d+)\s*%)|(?:(\d+)\s*%\s*(?:off\s+)?.*?(?:2da|segunda)\s+unidad)",
        low,
    )
    if m_2do:
        pct_val = int(m_2do.group(1) or m_2do.group(2))
        if 10 <= pct_val <= 95:
            d = pct_val / 100.0
            eff_unit = round(ref_price * (2.0 - d) / 2.0, 2)
            # Si el producto ya tiene un descuento directo (base_price) y ese precio ya es menor
            # o igual al descuento por volumen sobre lista (eff_unit >= base_price),
            # el supermercado aplica el descuento directo a cada unidad sin acumular.
            if eff_unit >= base_price and base_price < list_price:
                return None
            label = f"2do al {pct_val}%" + (" (Club/Tarjeta)" if is_club else "")
            return {
                "promo_etiqueta": label,
                "promo_tipo": "CLUB_PCT" if is_club else "BULK_PCT",
                "promo_min_qty": 2,
                "precio_promo_unit": eff_unit,
                "requiere_club": is_club,
            }

    m_nxm = re.search(r"\b([2346])\s*x\s*([12345])\b", low)
    if m_nxm:
        n, m = int(m_nxm.group(1)), int(m_nxm.group(2))
        if n > m > 0:
            eff_unit = round(ref_price * (m / n), 2)
            if eff_unit >= base_price and base_price < list_price:
                return None
            label = f"{n}x{m}" + (" (Tu Farmacity/Club)" if is_club else "")
            return {
                "promo_etiqueta": label,
                "promo_tipo": "CLUB_PCT" if is_club else "NXM",
                "promo_min_qty": n,
                "precio_promo_unit": eff_unit,
                "requiere_club": is_club,
            }

    m_pct = re.search(r"(\d{1,2})\s*%", low)
    if m_pct:
        pct_val = int(m_pct.group(1))
        if 5 <= pct_val <= 70:
            eff_unit = round(ref_price * (1.0 - pct_val / 100.0), 2)
            if is_club:
                if "carrefour" in low:
                    tag = f"{pct_val}% Tarjeta Carrefour"
                elif "dia" in low:
                    tag = f"{pct_val}% Club DIA"
                elif "farmacity" in low:
                    tag = f"{pct_val}% Tu Farmacity"
                else:
                    tag = f"{pct_val}% Club/Tarjeta"
                return {
                    "promo_etiqueta": tag,
                    "promo_tipo": "CLUB_PCT",
                    "promo_min_qty": 1,
                    "precio_promo_unit": eff_unit,
                    "requiere_club": True,
                }
            else:
                if eff_unit >= base_price and base_price < list_price:
                    return None
                return {
                    "promo_etiqueta": f"{pct_val}% OFF",
                    "promo_tipo": "DIRECT",
                    "promo_min_qty": 1,
                    "precio_promo_unit": eff_unit,
                    "requiere_club": False,
                }

    return None


def parse_vtex_product(
    prod: dict,
    store_name: str,
    fallback_url: str = "",
    grocery_only: bool = False,
    store_type: str = "supermarket",
) -> Optional[dict]:
    if not prod or not isinstance(prod, dict):
        return None
    items = prod.get("items") or []
    if not items:
        return None

    sku = None
    comm = None
    selected_seller = None
    for candidate_sku in items:
        sellers = candidate_sku.get("sellers") or []
        if not sellers:
            continue
        ordered_sellers = sorted(
            sellers,
            key=lambda s: not (str(s.get("sellerId") or "") == "1" or s.get("sellerDefault") is True),
        )
        for s in ordered_sellers:
            c_offer = s.get("commertialOffer") or {}
            avail = _safe_int(c_offer.get("AvailableQuantity"), 0)
            price = _safe_float(c_offer.get("Price"), 0.0)
            if avail > 0 and price > 0:
                sku = candidate_sku
                comm = c_offer
                selected_seller = s
                break
        if sku and comm:
            break

    if not sku or not comm:
        return None

    nombre = prod.get("productName") or sku.get("nameComplete") or sku.get("name") or ""
    marca = prod.get("brand") or "Genérico"
    cats = prod.get("categories") or []
    cats_str = ", ".join(c.strip("/") for c in cats) if cats else ""

    norm_nombre = _strip_accents(nombre)
    norm_cats = _strip_accents(cats_str)
    if grocery_only:
        if any(kw in norm_nombre or kw in norm_cats for kw in NON_GROCERY_MARKETPLACE_KEYWORDS):
            return None
        if any(ck in norm_cats for ck in NON_GROCERY_CATEGORY_KEYWORDS):
            return None

    # EAN extraction & normalization
    ean = sku.get("ean")
    if not ean:
        ref = sku.get("referenceId") or [{}]
        ean = ref[0].get("Value") if ref else None
    if not ean:
        ean_spec = prod.get("EAN")
        if isinstance(ean_spec, list) and ean_spec:
            ean = ean_spec[0]
    raw_ean = str(ean or "").replace("~", "").strip()
    ean = raw_ean

    # Model & Type extraction
    item_id = str(sku.get("itemId") or "")
    base_model, canon_model_key = extract_canonical_model(prod, sku, nombre, brand=marca)
    tipo = classify_product_type(cats_str, store_type=store_type)

    # Missing EAN handling: allow tech/electro through with synthetic model key or store item ID
    if not ean or ean.upper() in ("N/A", "NONE", "NULL", "0"):
        if grocery_only:
            return None
        if canon_model_key:
            ean = canon_model_key
        elif store_type in ("electro", "marketplace", "specialty") or tipo in ("electro", "ferreteria", "hogar"):
            clean_store = re.sub(r'[^A-Z0-9]', '', store_name.upper())
            ean = f"{clean_store}-{item_id}" if item_id else f"{clean_store}-{abs(hash(nombre)) % 10000000}"
        else:
            return None

    # Precio de góndola unitario oficial (commertialOffer.Price), con fallback a priceRange.sellingPrice
    pr_selling = (
        prod.get("priceRange", {})
        .get("sellingPrice", {})
        .get("lowPrice")
    )
    comm_price = _safe_float(comm.get("Price"), 0.0)
    pr_selling_val = _safe_float(pr_selling, 0.0)
    if comm_price > 0:
        base_price = comm_price
    elif pr_selling_val > 0:
        base_price = pr_selling_val
    else:
        base_price = 0.0

    if base_price <= 0:
        return None

    raw_list_price = _safe_float(comm.get("ListPrice"), base_price)
    if raw_list_price <= 0:
        raw_list_price = base_price

    seller_id = str((selected_seller or {}).get("sellerId") or "1")
    seller_name = str((selected_seller or {}).get("sellerName") or "")
    if (
        seller_id != "1"
        and store_name.lower() in ("carrefour", "masonline", "mas online", "más online")
        and raw_list_price > base_price * 3.5
    ):
        return None

    if raw_list_price > base_price * 4.0 or raw_list_price < base_price:
        list_price = base_price
    else:
        list_price = raw_list_price

    precio_venta = round(base_price, 2)
    descuento = round((1.0 - precio_venta / list_price) * 100.0, 1) if list_price > precio_venta else 0.0

    best_promo = {
        "promo_etiqueta": f"{int(round(descuento))}% OFF" if descuento >= 3 else None,
        "promo_tipo": "DIRECT" if descuento >= 3 else None,
        "promo_min_qty": 1,
        "precio_promo_unit": precio_venta,
        "requiere_club": False,
    }

    teasers = (
        (comm.get("PromotionTeasers") or [])
        + (comm.get("Teasers") or [])
        + (comm.get("teasers") or [])
    )
    for t in teasers:
        t_name = str(
            t.get("Name") or t.get("name") or t.get("<Name>k__BackingField") or ""
        ).strip()
        if not t_name:
            continue
        cand = _parse_active_teaser(t_name, precio_venta, list_price, force_club=_has_bin_restriction(t))
        if not cand:
            continue
        if best_promo["promo_tipo"] == "DIRECT" and cand["requiere_club"]:
            continue
        if (best_promo["promo_etiqueta"] is None
                or (best_promo["requiere_club"] and not cand["requiere_club"])
                or (cand["requiere_club"] == best_promo["requiere_club"]
                    and cand["precio_promo_unit"] < best_promo["precio_promo_unit"])):
            best_promo = cand

    precio_unidad, unidad = precio_venta, "un"
    cant, u_tit = extraer_unidad_titulo(nombre)
    if cant > 0 and (u_tit != "un" or cant > 1):
        precio_unidad, unidad = precio_venta / cant, u_tit
    p_unidad_norm, unidad_norm = normalizar_unidad(precio_unidad, unidad)
    p_unidad_norm = sanity_precio_unidad(precio_venta, p_unidad_norm, unidad_norm)

    link = prod.get("link") or fallback_url
    if link and link.startswith("/"):
        base_domain = _resolve_store_domain(store_name)
        link = f"{base_domain}{link}"
    elif not link and fallback_url:
        link = fallback_url

    if seller_id != "1" and link and "seller=" not in link:
        sep = "&" if "?" in link else "?"
        link = f"{link}{sep}seller={seller_id}"

    return {
        "ean": ean,
        "raw_ean": raw_ean,
        "nombre": nombre,
        "marca": marca,
        "modelo": base_model,
        "model_key": canon_model_key,
        "tipo": tipo,
        "imagen": ((sku.get("images") or [{}])[0] or {}).get("imageUrl"),
        "supermercado": store_name,
        "precio_venta": precio_venta,
        "precio_lista": round(list_price, 2),
        "descuento": descuento,
        "promo_etiqueta": best_promo["promo_etiqueta"],
        "promo_tipo": best_promo["promo_tipo"],
        "promo_min_qty": best_promo["promo_min_qty"],
        "precio_promo_unit": best_promo["precio_promo_unit"],
        "requiere_club": best_promo["requiere_club"],
        "precio_por_unidad": p_unidad_norm,
        "unidad_medida": unidad_norm,
        "categorias": normalizar_categoria(cats_str),
        "stock": _safe_int(comm.get("AvailableQuantity"), 0),
        "itemId": item_id,
        "seller_id": seller_id,
        "seller_name": seller_name,
        "unit_multiplier": _safe_float(sku.get("unitMultiplier"), 1.0),
        "link": link,
        "fecha": datetime.now(timezone.utc).isoformat(),
    }


def _parse_ars_price(raw_txt: str) -> Optional[float]:
    if not raw_txt:
        return None
    s = str(raw_txt).lower().split("c/u")[0].strip()
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) == 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        val = float(s)
        return round(val, 2) if val > 0 else None
    except Exception:
        return None


def parse_coto_discounts(precio_lista: float, descuentos_raw: list) -> dict:
    res = {
        "precio_venta": round(precio_lista, 2),
        "promo_etiqueta": None,
        "promo_tipo": None,
        "promo_min_qty": 1,
        "precio_promo_unit": round(precio_lista, 2),
        "requiere_club": False,
    }
    if not descuentos_raw or not isinstance(descuentos_raw, list):
        return res

    try:
        items = json.loads(descuentos_raw[0]) if isinstance(descuentos_raw[0], str) else descuentos_raw
    except Exception:
        return res
    if not isinstance(items, list) or not items:
        return res

    for d in items:
        if not isinstance(d, dict):
            continue
        desc_txt = str(d.get("textoDescuento") or d.get("descripcion") or "").strip()
        img_desc = str(d.get("imagenDescuento") or "").lower()
        comentarios = str(d.get("comentarios") or "").lower()
        p_dto = _parse_ars_price(d.get("precioDescuento", ""))

        is_comunidad = (
            "comunidad" in img_desc
            or "comunidad" in desc_txt.lower()
            or "comunidad" in comentarios
            or "tarjeta" in img_desc
            or "banco" in img_desc
        )

        low_txt = desc_txt.lower()
        m_2da = re.search(r"2d[ao].*?(\d+)\s*%|(\d+)\s*%.*?2d[ao]", low_txt)
        m_nxm = re.search(r"\b([2346])\s*x\s*([12345])\b", low_txt)

        if m_2da:
            if is_comunidad and res["promo_etiqueta"] and not res["requiere_club"]:
                continue
            pct = float(m_2da.group(1) or m_2da.group(2)) / 100.0
            eff = p_dto or round(precio_lista * (2.0 - pct) / 2.0, 2)
            res.update({
                "promo_etiqueta": f"2da al {int(pct * 100)}%" + (" Comunidad" if is_comunidad else ""),
                "promo_tipo": "CLUB_PCT" if is_comunidad else "BULK_PCT",
                "promo_min_qty": 2,
                "precio_promo_unit": eff,
                "requiere_club": is_comunidad,
            })
            continue

        if m_nxm:
            if is_comunidad and res["promo_etiqueta"] and not res["requiere_club"]:
                continue
            n, m = int(m_nxm.group(1)), int(m_nxm.group(2))
            if n > m > 0:
                eff = p_dto or round(precio_lista * (m / n), 2)
                res.update({
                    "promo_etiqueta": f"{n}x{m}" + (" Comunidad" if is_comunidad else ""),
                    "promo_tipo": "NXM",
                    "promo_min_qty": n,
                    "precio_promo_unit": eff,
                    "requiere_club": is_comunidad,
                })
                continue

        if p_dto and p_dto < precio_lista:
            pct_calc = int(round((1.0 - p_dto / precio_lista) * 100))
            if not is_comunidad:
                res["precio_venta"] = p_dto
                if res["requiere_club"] or p_dto <= res["precio_promo_unit"]:
                    res["precio_promo_unit"] = p_dto
                    res["promo_etiqueta"] = f"{pct_calc}% OFF"
                    res["promo_tipo"] = "DIRECT"
                    res["promo_min_qty"] = 1
                    res["requiere_club"] = False
            else:
                if (res["promo_etiqueta"] is None or res["requiere_club"]) and p_dto < res["precio_promo_unit"]:
                    res["precio_promo_unit"] = p_dto
                    res["promo_etiqueta"] = f"{pct_calc}% Comunidad Coto"
                    res["promo_tipo"] = "CLUB_PCT"
                    res["promo_min_qty"] = 1
                    res["requiere_club"] = True

    return res


def parse_coto_record(
    data: dict,
    item_id: str = "",
    url: str = "",
    grocery_only: bool = False,
    store_type: str = "supermarket",
) -> Optional[dict]:
    record = None
    if isinstance(data, dict) and ("attributes" in data or "records" in data):
        record = data
    else:
        try:
            for b in data["contents"][0]["Main"]:
                if "record" in b:
                    record = b["record"]
                    break
        except Exception:
            return None
    if not record:
        return None

    attrs = dict(record.get("attributes") or {})
    inner_recs = record.get("records") or []
    if inner_recs and isinstance(inner_recs[0], dict):
        attrs.update(inner_recs[0].get("attributes") or {})

    nombre = (attrs.get("product.displayName") or attrs.get("sku.displayName") or [""])[0]
    if not nombre:
        return None
    marca = (attrs.get("product.brand") or attrs.get("product.MARCA") or ["Genérico"])[0]
    imagen = ((attrs.get("product.largeImage.url") or [""])[0]
              or (attrs.get("product.mediumImage.url") or [""])[0])

    cats = ((attrs.get("parentCategory.displayName") or [""])[0]
            or (attrs.get("product.category") or [""])[0])
    cats_str = str(cats or "")
    norm_nombre = _strip_accents(nombre)
    norm_cats = _strip_accents(cats_str)

    # Contextual grocery filter unlocking
    if grocery_only:
        if any(kw in norm_nombre or kw in norm_cats for kw in NON_GROCERY_MARKETPLACE_KEYWORDS):
            return None
        if any(ck in norm_cats for ck in NON_GROCERY_CATEGORY_KEYWORDS):
            return None

    p_list = _safe_float((attrs.get("sku.activePrice") or ["0"])[0], 0.0)
    if p_list <= 0:
        return None

    promo = parse_coto_discounts(p_list, attrs.get("product.dtoDescuentos", []))
    p_venta = promo["precio_venta"]

    if not item_id:
        rec_id = (attrs.get("record.id") or attrs.get("product.repositoryId") or [""])[0]
        m = re.search(r"(\d+)", str(rec_id))
        item_id = m.group(1) if m else str(rec_id)

    raw_ean = (attrs.get("product.eanPrincipal") or [""])[0].strip()
    ean = raw_ean

    # Model & Type extraction for Coto
    base_model, canon_model_key = extract_canonical_model({}, {}, nombre, brand=marca)
    tipo = classify_product_type(cats_str, store_type=store_type)

    if not ean:
        if grocery_only:
            return None
        if canon_model_key:
            ean = canon_model_key
        else:
            ean = f"COTO-{item_id}"

    precio_unidad, unidad = p_venta, "un"
    cant, u_tit = extraer_unidad_titulo(nombre)
    if cant > 0 and (u_tit != "un" or cant > 1):
        precio_unidad, unidad = p_venta / cant, u_tit
    p_unidad_norm, unidad_norm = normalizar_unidad(precio_unidad, unidad)
    p_unidad_norm = sanity_precio_unidad(p_venta, p_unidad_norm, unidad_norm)

    descuento = round((1.0 - p_venta / p_list) * 100.0, 1) if p_list > p_venta else 0.0

    rec_state = record.get("detailsAction", {}).get("recordState") or ""
    if not url:
        if rec_state:
            clean_state = rec_state.split("?")[0]
            url = f"https://www.cotodigital.com.ar/sitios/cdigi/productos{clean_state}"
        else:
            url = f"https://www.cotodigital.com.ar/sitios/cdigi/productos/_/A-{item_id}-{item_id}-200"

    return {
        "ean": ean,
        "raw_ean": raw_ean,
        "nombre": nombre,
        "marca": marca,
        "modelo": base_model,
        "model_key": canon_model_key,
        "tipo": tipo,
        "imagen": imagen,
        "supermercado": "Coto",
        "precio_venta": p_venta,
        "precio_lista": round(p_list, 2),
        "descuento": descuento,
        "promo_etiqueta": promo["promo_etiqueta"],
        "promo_tipo": promo["promo_tipo"],
        "promo_min_qty": promo["promo_min_qty"],
        "precio_promo_unit": promo["precio_promo_unit"],
        "requiere_club": promo["requiere_club"],
        "precio_por_unidad": p_unidad_norm,
        "unidad_medida": unidad_norm,
        "categorias": normalizar_categoria(cats_str),
        "stock": 1,
        "itemId": str(item_id),
        "link": url,
        "fecha": datetime.now(timezone.utc).isoformat(),
    }
