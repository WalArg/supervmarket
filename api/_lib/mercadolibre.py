"""Módulo de integración con Mercado Libre Supermercado y Catálogo (MLA).

Permite consultar en vivo productos, precios oficiales, envíos FULL y ofertas
utilizando la API oficial de Mercado Libre Developers con Client Credentials.
"""

import os
import time
import asyncio
import urllib.parse
import httpx
from .parsers import (
    extraer_unidad_titulo,
    normalizar_unidad,
    sanity_precio_unidad,
)

MELI_CLIENT_ID = os.getenv("MELI_CLIENT_ID", "6947318731363625")
MELI_CLIENT_SECRET = os.getenv("MELI_CLIENT_SECRET", "g6qrGOxdw6iIatBY6osc35Jq6wVqE9PS")

_CACHED_TOKEN: str | None = None
_TOKEN_EXPIRES_AT: float = 0.0


async def get_meli_token(client: httpx.AsyncClient) -> str | None:
    """Obtiene o reutiliza el token de acceso oficial de la aplicación de Mercado Libre."""
    global _CACHED_TOKEN, _TOKEN_EXPIRES_AT
    now = time.time()
    if _CACHED_TOKEN and now < _TOKEN_EXPIRES_AT:
        return _CACHED_TOKEN

    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": MELI_CLIENT_ID,
        "client_secret": MELI_CLIENT_SECRET,
    }
    try:
        r = await client.post(url, data=payload, timeout=8.0)
        if r.status_code == 200:
            data = r.json()
            _CACHED_TOKEN = data["access_token"]
            _TOKEN_EXPIRES_AT = now + float(data.get("expires_in", 21600)) - 180
            return _CACHED_TOKEN
    except Exception:
        pass
    return None


def parse_meli_product(prod: dict, item: dict) -> dict | None:
    """Convierte un producto y su mejor oferta en el formato unificado de SuperVmarket."""
    try:
        price = float(item.get("price") or 0)
        if price <= 0:
            return None

        # Atributos de catálogo certificados por Mercado Libre
        attrs_map = {a.get("id"): a.get("value_name") for a in prod.get("attributes", [])}
        manual_title = attrs_map.get("MANUAL_TITLE")
        raw_name = prod.get("name") or ""
        title = manual_title if (manual_title and len(manual_title) > len(raw_name)) else raw_name

        # Detección de multipacks en atributos (ej: UNITS_PER_PACK = 3 o 6)
        upp_str = str(attrs_map.get("UNITS_PER_PACK") or attrs_map.get("PACKAGE_UNITS_COUNT") or "1")
        upp = int(upp_str) if upp_str.isdigit() else 1
        import re
        if upp > 1 and not re.search(r"\b(?:pack|caja|x\s*\d+|\d+\s*botellas?|\d+\s*unidades?)\b", title, re.IGNORECASE):
            title = f"{title} (Pack x{upp})"

        item_id = item.get("item_id") or ""
        orig_price = item.get("original_price")
        orig_price_f = float(orig_price) if orig_price else price

        # Extraer atributos canónicos: marca, EAN/GTIN
        brand = attrs_map.get("BRAND")
        ean = None
        gtin_val = str(attrs_map.get("GTIN") or "").strip()
        # GTIN puede contener varios EANs separados por coma en MeLi
        for candidate in gtin_val.split(","):
            c_clean = candidate.strip()
            if c_clean.isdigit() and 8 <= len(c_clean) <= 14:
                ean = c_clean
                break

        # Imagen
        pictures = prod.get("pictures") or []
        image_url = pictures[0].get("url") if pictures else None
        if image_url and image_url.startswith("http://"):
            image_url = "https://" + image_url[7:]

        # Envíos y beneficios
        shipping = item.get("shipping") or {}
        is_full = shipping.get("logistic_type") == "fulfillment"
        free_shipping = shipping.get("free_shipping") is True

        promo_label = None
        if orig_price_f > price:
            pct = round((1 - price / orig_price_f) * 100)
            if pct >= 5:
                promo_label = f"{pct}% OFF"
        elif is_full:
            promo_label = "⚡ Envío FULL"
        elif free_shipping:
            promo_label = "🚚 Envío Gratis"

        # 1. Priorizar volumen/peso total certificado de Mercado Libre (ej: "2.25 L" o "1 kg")
        net_vol = attrs_map.get("NET_VOLUME") or attrs_map.get("TOTAL_VOLUME")
        net_weight = attrs_map.get("NET_WEIGHT") or attrs_map.get("TOTAL_WEIGHT")

        cant, unidad = None, None
        if net_vol:
            c, u = extraer_unidad_titulo(f"Prod {net_vol}")
            if c and u in ("l", "ml", "cc"):
                cant, unidad = c, u
        elif net_weight:
            c, u = extraer_unidad_titulo(f"Prod {net_weight}")
            if c and u in ("kg", "g", "gr"):
                cant, unidad = c, u

        # 2. Si MeLi no tenía atributo neto certificado, extraer del título completo
        if not cant or not unidad:
            cant, unidad = extraer_unidad_titulo(title)

        cant_norm, unidad_norm = normalizar_unidad(cant, unidad)

        unit_p = None
        if cant_norm and cant_norm > 0 and unidad_norm in ("kg", "l", "un"):
            raw_u = price / cant_norm
            if sanity_precio_unidad(price, raw_u, unidad_norm):
                unit_p = round(raw_u, 2)

        permalink = f"https://articulo.mercadolibre.com.ar/{item_id}"

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
            "imagen": image_url,
            "requires_club": False,
            "is_full": is_full,
        }
    except Exception:
        return None


async def fetch_mercadolibre_live(
    client: httpx.AsyncClient,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Consulta productos en vivo desde el catálogo oficial de Mercado Libre."""
    token = await get_meli_token(client)
    if not token:
        return []

    q_clean = query.strip()
    is_ean = q_clean.isdigit() and 8 <= len(q_clean) <= 14
    if is_ean:
        url = f"https://api.mercadolibre.com/products/search?status=active&site_id=MLA&product_identifier={q_clean}"
    else:
        q_enc = urllib.parse.quote(q_clean)
        url = f"https://api.mercadolibre.com/products/search?status=active&site_id=MLA&q={q_enc}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "SuperVmarket/2.0",
    }

    try:
        r = await client.get(url, headers=headers, timeout=4.5)
        if r.status_code != 200:
            return []
        data = r.json()
        products = data.get("results", [])
        if not products:
            return []

        # Consultar precios en paralelo para los primeros productos del catálogo
        async def _fetch_product_best_item(prod: dict) -> dict | None:
            pid = prod.get("id")
            if not pid:
                return None
            it_url = f"https://api.mercadolibre.com/products/{pid}/items"
            try:
                ir = await client.get(it_url, headers=headers, timeout=3.5)
                if ir.status_code == 200:
                    items = ir.json().get("results", [])
                    if items:
                        # Ordenar por menor precio para traer la mejor oferta disponible en MeLi
                        best_item = min(items, key=lambda x: float(x.get("price") or 999999))
                        return parse_meli_product(prod, best_item)
            except Exception:
                pass
            return None

        tasks = [_fetch_product_best_item(p) for p in products[:limit]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if isinstance(r, dict) and r]
    except Exception:
        return []
