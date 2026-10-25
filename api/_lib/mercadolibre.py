"""Módulo de integración con Mercado Libre Supermercado (MLA1403).

Permite consultar en vivo precios, ofertas con Envío FULL y stock oficial de Mercado Libre
para contrastar contra los supermercados físicos tradicionales (Coto, Carrefour, Día, Jumbo).
"""

import os
import time
import urllib.parse
import httpx
from .parsers import (
    extraer_unidad_titulo,
    normalizar_unidad,
    sanity_precio_unidad,
)

MELI_CLIENT_ID = os.getenv("MELI_CLIENT_ID", "6947318731363625")
MELI_CLIENT_SECRET = os.getenv("MELI_CLIENT_SECRET", "g6qrGOxdw6iIatBY6osc35Jq6wVqE9PS")
MELI_REDIRECT_URI = os.getenv("MELI_REDIRECT_URI", "https://vsupermarket.vercel.app")

# Persistencia en memoria y archivo de tokens
_TOKEN_STATE: dict = {
    "access_token": None,
    "refresh_token": os.getenv("MELI_REFRESH_TOKEN", ""),
    "expires_at": 0.0,
}

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "meli_token.json")


def _load_saved_token():
    try:
        import json
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _TOKEN_STATE["access_token"] = data.get("access_token")
                _TOKEN_STATE["refresh_token"] = data.get("refresh_token")
                _TOKEN_STATE["expires_at"] = data.get("expires_at", 0.0)
    except Exception:
        pass


_load_saved_token()


def save_token_state(access_token: str, refresh_token: str, expires_in: int):
    import json
    _TOKEN_STATE["access_token"] = access_token
    _TOKEN_STATE["refresh_token"] = refresh_token
    _TOKEN_STATE["expires_at"] = time.time() + expires_in - 120  # Margen de 2 min
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(_TOKEN_STATE, f)
    except Exception:
        pass


async def exchange_auth_code(code: str) -> bool:
    """Intercambia el código de autorización temporal por access_token y refresh_token permanentes."""
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": MELI_CLIENT_ID,
        "client_secret": MELI_CLIENT_SECRET,
        "code": code.strip(),
        "redirect_uri": MELI_REDIRECT_URI,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(url, data=payload)
            if r.status_code == 200:
                data = r.json()
                save_token_state(
                    data["access_token"],
                    data.get("refresh_token", ""),
                    data.get("expires_in", 21600),
                )
                return True
        except Exception:
            pass
    return False


async def refresh_access_token() -> str | None:
    """Refresca el access_token usando el refresh_token permanente."""
    rf = _TOKEN_STATE.get("refresh_token")
    if not rf:
        # Intentar flujo client_credentials como fallback
        url = "https://api.mercadolibre.com/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": MELI_CLIENT_ID,
            "client_secret": MELI_CLIENT_SECRET,
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                r = await client.post(url, data=payload)
                if r.status_code == 200:
                    data = r.json()
                    _TOKEN_STATE["access_token"] = data["access_token"]
                    _TOKEN_STATE["expires_at"] = time.time() + data.get("expires_in", 21600) - 120
                    return data["access_token"]
            except Exception:
                return None

    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": MELI_CLIENT_ID,
        "client_secret": MELI_CLIENT_SECRET,
        "refresh_token": rf,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(url, data=payload)
            if r.status_code == 200:
                data = r.json()
                save_token_state(
                    data["access_token"],
                    data.get("refresh_token", rf),
                    data.get("expires_in", 21600),
                )
                return data["access_token"]
        except Exception:
            pass
    return None


async def get_valid_token() -> str | None:
    if _TOKEN_STATE.get("access_token") and time.time() < _TOKEN_STATE.get("expires_at", 0):
        return _TOKEN_STATE["access_token"]
    return await refresh_access_token()


def parse_meli_item(item: dict) -> dict | None:
    """Parsea un resultado de Mercado Libre al formato estándar de SuperVmarket."""
    try:
        title = item.get("title") or ""
        price = float(item.get("price") or 0)
        if price <= 0:
            return None

        orig_price = item.get("original_price")
        orig_price_f = float(orig_price) if orig_price else price

        # Identificar EAN / GTIN de los atributos oficiales
        ean = None
        brand = None
        for a in item.get("attributes", []):
            aid = a.get("id")
            if aid == "GTIN":
                val = str(a.get("value_name") or "").strip()
                if val.isdigit() and 8 <= len(val) <= 14:
                    ean = val
            elif aid == "BRAND":
                brand = a.get("value_name")

        item_id = item.get("id") or ""
        permalink = item.get("permalink") or f"https://articulo.mercadolibre.com.ar/{item_id}"
        thumbnail = item.get("thumbnail") or ""
        if thumbnail.startswith("http://"):
            thumbnail = "https://" + thumbnail[7:]
        # Imagen de mayor calidad
        thumbnail = thumbnail.replace("-I.jpg", "-O.jpg")

        shipping = item.get("shipping") or {}
        is_full = shipping.get("logistic_type") == "fulfillment"
        free_ship = shipping.get("free_shipping") is True

        # Etiqueta de promoción
        promo_label = None
        if orig_price_f > price:
            pct = round((1 - price / orig_price_f) * 100)
            if pct >= 5:
                promo_label = f"{pct}% OFF"
        elif is_full:
            promo_label = "⚡ Envío FULL"
        elif free_ship:
            promo_label = "🚚 Envío Gratis"

        cant, unidad = extraer_unidad_titulo(title)
        cant_norm, unidad_norm = normalizar_unidad(cant, unidad)

        unit_p = None
        if cant_norm and cant_norm > 0 and unidad_norm in ("kg", "l", "un"):
            raw_u = price / cant_norm
            if sanity_precio_unidad(price, raw_u, unidad_norm):
                unit_p = round(raw_u, 2)

        return {
            "supermercado": "MercadoLibre",
            "ean": ean or f"MELI_{item_id}",
            "sku": item_id,
            "nombre": title,
            "marca": brand or "Mercado Libre",
            "precio": price,
            "precio_venta": price,
            "precio_lista": orig_price_f,
            "unit_price": unit_p,
            "unit_type": unidad_norm if unit_p else None,
            "cantidad_unidades": cant_norm,
            "promo_label": promo_label,
            "discount": round((1 - price / orig_price_f) * 100) if orig_price_f > price else 0,
            "stock": 100,
            "url": permalink,
            "imagen": thumbnail,
            "requires_club": False,
            "is_full": is_full,
        }
    except Exception:
        return None


async def fetch_mercadolibre_live(
    client: httpx.AsyncClient,
    query: str,
    limit: int = 15,
) -> list[dict]:
    """Consulta en vivo productos de supermercado en Mercado Libre."""
    token = await get_valid_token()
    if not token:
        return []

    q_enc = urllib.parse.quote(query.strip())
    # Búsqueda restringida a la categoría Alimentos y Bebidas / Supermercado (MLA1403)
    url = f"https://api.mercadolibre.com/sites/MLA/search?q={q_enc}&category=MLA1403&limit={limit}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "SuperVmarket/1.0",
    }

    try:
        r = await client.get(url, headers=headers)
        if r.status_code != 200:
            return []
        data = r.json()
        results = data.get("results", [])
        out = []
        for raw in results:
            parsed = parse_meli_item(raw)
            if parsed:
                out.append(parsed)
        return out
    except Exception:
        return []
