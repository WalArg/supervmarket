"""Configuración de tiendas: dominios VTEX, canales de venta (sc), soporte de carrito y mínimos."""

# Tiendas VTEX -> dominio público (para guest-link y simulación de carrito).
VTEX_DOMAINS = {
    "Jumbo": "https://www.jumbo.com.ar",
    "Disco": "https://www.disco.com.ar",
    "Vea": "https://www.vea.com.ar",
    "Carrefour": "https://www.carrefour.com.ar",
    "Dia": "https://diaonline.supermercadosdia.com.ar",
    "Masonline": "https://www.masonline.com.ar",
    "Farmacity": "https://www.farmacity.com",
    "Simplicity": "https://www.simplicity.com.ar",
    "Farmaonline": "https://www.farmaonline.com",
    "Farmaplus": "https://www.farmaplus.com.ar",
}

# Canal de venta (Sales Channel `sc`) real verificado en los payloads de cada tienda VTEX.
# Crítico: Jumbo=32, Disco=33, Vea=34, Farmacity=4. Sin el sc correcto, VTEX devuelve ORD027.
VTEX_SALES_CHANNELS = {
    "Jumbo": "32",
    "Disco": "33",
    "Vea": "34",
    "Carrefour": "1",
    "Dia": "1",
    "Masonline": "1",
    "Farmacity": "4",
    "Simplicity": "1",
    "Farmaonline": "1",
    "Farmaplus": "1",
}

# Coto NO es VTEX -> es "solo comparar" (abre los productos pero no tiene guest-link VTEX).
COMPARE_ONLY = {"Coto"}

# Umbrales de envío gratis (ARS).
FREE_SHIPPING = {
    "Jumbo": 35000,
    "Disco": 35000,
    "Vea": 30000,
    "Carrefour": 30000,
    "Dia": 25000,
    "Masonline": 30000,
    "Coto": 30000,
    "Farmacity": 25000,
    "Simplicity": 25000,
    "Farmaonline": 25000,
    "Farmaplus": 25000,
    "MercadoLibre": 65000,
    "TheFoodMarket": 28000,
    "LaBarraCCU": 25000,
    "LaBarata": 35000,
    "TonelPrivado": 40000,
    "DePastura": 45000,
    "ArcorEnCasa": 35000,
}

# Costo estimado de envío a domicilio (ARS) cuando no se alcanza el umbral de envío gratis.
SHIPPING_COST = {
    "Jumbo": 5500,
    "Disco": 5500,
    "Vea": 4900,
    "Carrefour": 4800,
    "Dia": 4599,
    "Masonline": 4900,
    "Coto": 5200,
    "Farmacity": 3900,
    "Simplicity": 3900,
    "Farmaonline": 3900,
    "Farmaplus": 3900,
    "MercadoLibre": 4999,
    "TheFoodMarket": 4500,
    "LaBarraCCU": 4500,
    "LaBarata": 4500,
    "TonelPrivado": 4900,
    "DePastura": 5200,
    "ArcorEnCasa": 4500,
}


import os
import urllib.parse

MELI_AFFILIATE_TOOL = os.getenv("MELI_AFFILIATE_TOOL", "43872651")
DEFAULT_AFFILIATE_SOURCE = os.getenv("AFFILIATE_UTM_SOURCE", "supervmarket")
DEFAULT_AFFILIATE_MEDIUM = os.getenv("AFFILIATE_UTM_MEDIUM", "affiliate")
VTEX_AFILIADO_ID = os.getenv("VTEX_AFILIADO_ID", "supervmarket")

RETAILER_AFFILIATE_CONFIG = {
    "Carrefour": {
        "network": "direct",
        "cpa_rate": 0.025,
        "cookie_days": 30,
        "campaign": "smart_cart_carrefour",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_carrefour",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Dia": {
        "network": "soicos",
        "cpa_rate": 0.030,
        "cookie_days": 30,
        "campaign": "smart_cart_dia",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_dia",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Jumbo": {
        "network": "cencosud_direct",
        "cpa_rate": 0.020,
        "cookie_days": 15,
        "campaign": "smart_cart_jumbo",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_jumbo",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Disco": {
        "network": "cencosud_direct",
        "cpa_rate": 0.020,
        "cookie_days": 15,
        "campaign": "smart_cart_disco",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_disco",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Vea": {
        "network": "cencosud_direct",
        "cpa_rate": 0.020,
        "cookie_days": 15,
        "campaign": "smart_cart_vea",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_vea",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Masonline": {
        "network": "direct",
        "cpa_rate": 0.025,
        "cookie_days": 30,
        "campaign": "smart_cart_masonline",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_masonline",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Farmacity": {
        "network": "direct",
        "cpa_rate": 0.035,
        "cookie_days": 30,
        "campaign": "smart_cart_farmacity",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_farmacity",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Simplicity": {
        "network": "direct",
        "cpa_rate": 0.035,
        "cookie_days": 30,
        "campaign": "smart_cart_simplicity",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_simplicity",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Farmaonline": {
        "network": "direct",
        "cpa_rate": 0.030,
        "cookie_days": 30,
        "campaign": "smart_cart_farmaonline",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_farmaonline",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "Farmaplus": {
        "network": "direct",
        "cpa_rate": 0.030,
        "cookie_days": 30,
        "campaign": "smart_cart_farmaplus",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "smart_cart_farmaplus",
            "utm_term": "optimizado",
            "afiliado_id": VTEX_AFILIADO_ID,
        },
    },
    "MercadoLibre": {
        "network": "meli_partners",
        "cpa_rate": 0.040,
        "cookie_days": 1,
        "campaign": "meli_smart_cart",
        "params": {
            "matt_tool": MELI_AFFILIATE_TOOL,
            "matt_word": "sv_smart_cart",
            "matt_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "meli_smart_cart",
        },
    },
    "Coto": {
        "network": "coto_direct",
        "cpa_rate": 0.015,
        "cookie_days": 7,
        "campaign": "coto_smart_cart",
        "params": {
            "utm_source": DEFAULT_AFFILIATE_SOURCE,
            "utm_medium": DEFAULT_AFFILIATE_MEDIUM,
            "utm_campaign": "coto_smart_cart",
            "utm_term": "copiar_lista",
        },
    },
}


def supports_cart(store: str) -> bool:
    return store in VTEX_DOMAINS


def sales_channel(store: str) -> str:
    return VTEX_SALES_CHANNELS.get(store, "1")


def free_shipping_threshold(store: str) -> int:
    return FREE_SHIPPING.get(store, 0)


def estimated_shipping_cost(store: str) -> float:
    return float(SHIPPING_COST.get(store, 4900))


def decorate_store_url(
    url: str | None,
    store_key: str,
    link_type: str = "checkout",
    click_id: str | None = None,
    extra_params: dict | None = None,
) -> str:
    """Decora URLs salientes hacia tiendas o Mercado Libre con parámetros oficiales de afiliación y UTM.

    Garantiza:
    1. Preservación estricta del orden y repetición de tuplas query de VTEX (sku=..&qty=..&seller=..&sc=..).
    2. Idempotencia: si los parámetros ya están presentes, no los duplica.
    3. Preservación de fragmentos hash (#).
    4. Cero perturbación del catálogo oficial ni disponibilidad de ítems.
    """
    if not url:
        return ""
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        return clean_url

    parsed = urllib.parse.urlsplit(clean_url)
    existing_qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    normalized_store = (store_key or "").strip()
    store_lower = normalized_store.lower().replace(" ", "").replace("_", "")
    is_meli = "mercadolibre" in store_lower or "mercadolibre.com" in parsed.netloc
    is_coto = "coto" in store_lower or "cotodigital" in parsed.netloc

    # Seleccionar configuración o construir parámetros según la tienda y tipo de link
    injected: dict[str, str] = {}
    matched_config = RETAILER_AFFILIATE_CONFIG.get(normalized_store)

    if not matched_config:
        # Intento de matching insensible a mayúsculas
        for k, v in RETAILER_AFFILIATE_CONFIG.items():
            if k.lower() == normalized_store.lower():
                matched_config = v
                break

    if is_meli:
        sub_word = "sv_item" if link_type == "item" else "sv_smart_cart"
        injected["matt_tool"] = MELI_AFFILIATE_TOOL
        injected["matt_word"] = sub_word
        injected["matt_source"] = DEFAULT_AFFILIATE_SOURCE
        injected["utm_source"] = DEFAULT_AFFILIATE_SOURCE
        injected["utm_medium"] = DEFAULT_AFFILIATE_MEDIUM
        injected["utm_campaign"] = "meli_item" if link_type == "item" else "meli_smart_cart"
    elif is_coto:
        injected["utm_source"] = DEFAULT_AFFILIATE_SOURCE
        injected["utm_medium"] = DEFAULT_AFFILIATE_MEDIUM
        injected["utm_campaign"] = "coto_item" if link_type == "item" else "coto_smart_cart"
        injected["utm_term"] = "item" if link_type == "item" else "copiar_lista"
    elif matched_config and "params" in matched_config:
        injected = dict(matched_config["params"])
        if link_type == "item":
            store_slug = normalized_store.lower()
            injected["utm_campaign"] = f"item_{store_slug}"
            injected["utm_term"] = "item"
    else:
        store_slug = normalized_store.lower() if normalized_store else "store"
        injected["utm_source"] = DEFAULT_AFFILIATE_SOURCE
        injected["utm_medium"] = DEFAULT_AFFILIATE_MEDIUM
        injected["utm_campaign"] = f"smart_cart_{store_slug}" if link_type != "item" else f"item_{store_slug}"
        injected["utm_term"] = "optimizado" if link_type != "item" else "item"
        if VTEX_AFILIADO_ID:
            injected["afiliado_id"] = VTEX_AFILIADO_ID

    if click_id:
        injected["subid"] = click_id

    if extra_params:
        for k, v in extra_params.items():
            if v is not None:
                injected[k] = str(v)

    # Filtrar únicamente los parámetros que NO existan en la URL original (evita duplicación)
    params_to_add = {k: v for k, v in injected.items() if k not in existing_qs}
    if not params_to_add:
        return clean_url

    encoded_add = urllib.parse.urlencode(params_to_add)
    new_query = f"{parsed.query}&{encoded_add}" if parsed.query else encoded_add
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))

