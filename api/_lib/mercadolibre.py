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
from .stores import decorate_store_url

MELI_CLIENT_ID = os.getenv("MELI_CLIENT_ID", "6947318731363625")
MELI_CLIENT_SECRET = os.getenv("MELI_CLIENT_SECRET", "g6qrGOxdw6iIatBY6osc35Jq6wVqE9PS")

_CACHED_TOKEN: str | None = None
_TOKEN_EXPIRES_AT: float = 0.0
_SELLER_REP_CACHE: dict[int, dict] = {}

# Dominios o prefijos de dominios en Mercado Libre ajenos a supermercado / consumo masivo
NON_SUPERMARKET_DOMAIN_PREFIXES = (
    "MLA-VEHICLE_",
    "MLA-AUTO_",
    "MLA-MOTORCYCLE_",
    "MLA-CAR_",
    "MLA-KITCHEN_",
    "MLA-POUFS",
    "MLA-PILLOWS",
    "MLA-CUSHIONS",
    "MLA-SOAP_HOLDERS",
    "MLA-MANUAL_SOAP_",
    "MLA-MANUAL_BEER_",
    "MLA-BEER_FAUCETS",
    "MLA-DISHES_",
    "MLA-DRINKING_GLASSES",
    "MLA-OIL_AND_VINEGAR_",
    "MLA-BOOKS",
    "MLA-CLOTHING",
    "MLA-CELLPHONES",
    "MLA-TOOLS",
    "MLA-TOYS",
    "MLA-NAIL_POLISH",
    "MLA-TOILETRY_BAGS",
    "MLA-HEADPHONES",
    "MLA-AUDIO_",
    "MLA-COMPUTER_",
    "MLA-FOOTWEAR",
)


def _is_supermarket_domain(domain_id: str | None) -> bool:
    """Descarta dominios que pertenecen a rubros ajenos a supermercado (automotor, bazar, accesorios)."""
    if not domain_id:
        return True
    dom = domain_id.upper()
    for prefix in NON_SUPERMARKET_DOMAIN_PREFIXES:
        if dom.startswith(prefix):
            return False
    bad_tokens = (
        "AIR_FRESHENER", "VEHICLE", "AUTO_", "MOTORCYCLE", "FILTER", "RADIATOR",
        "DISPENSER", "HOLDER", "SLICER", "GRATER", "CUSHION", "PILLOW", "POUF",
        "POLISH", "TOILETRY", "HEADPHONE", "DRINKING_GLASS",
    )
    for tok in bad_tokens:
        if tok in dom:
            return False
    return True


async def _ensure_seller_reputations(client: httpx.AsyncClient, token: str, seller_ids: list[int]):
    """Consulta en batch y cachea la reputación y datos comerciales oficiales de los vendedores de MeLi."""
    missing = [sid for sid in seller_ids if sid and sid not in _SELLER_REP_CACHE]
    if not missing:
        return
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    for chunk in [missing[i:i + 20] for i in range(0, len(missing), 20)]:
        ids_str = ",".join(str(s) for s in chunk)
        try:
            r = await client.get(f"https://api.mercadolibre.com/users?ids={ids_str}", headers=headers, timeout=2.5)
            if r.status_code == 200:
                for entry in r.json():
                    b = entry.get("body", {})
                    sid = b.get("id")
                    if sid:
                        rep = b.get("seller_reputation", {})
                        _SELLER_REP_CACHE[sid] = {
                            "level_id": rep.get("level_id"),
                            "power_seller_status": rep.get("power_seller_status"),
                            "nickname": b.get("nickname") or "",
                            "user_type": b.get("user_type") or "",
                        }
        except Exception:
            pass


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


def parse_meli_product(prod: dict, item: dict, seller_meta: dict | None = None) -> dict | None:
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
                if len(c_clean) == 14 and c_clean.startswith("0"):
                    c_clean = c_clean[1:]
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

        prod_id = prod.get("id")
        # Enlace directo al vendedor/publicación real para respetar el precio más bajo exacto
        if item_id:
            clean_item_id = (
                f"MLA-{item_id[3:]}"
                if (item_id.startswith("MLA") and not item_id.startswith("MLA-"))
                else item_id
            )
            permalink = f"https://articulo.mercadolibre.com.ar/{clean_item_id}"
        elif prod_id and str(prod_id).startswith("MLA"):
            permalink = f"https://www.mercadolibre.com.ar/p/{prod_id}"
        else:
            permalink = "https://www.mercadolibre.com.ar/supermercado"

        permalink = decorate_store_url(permalink, "MercadoLibre", "item")

        result = {
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
            "link": permalink,
            "imagen": image_url,
            "requires_club": False,
            "is_full": is_full,
            "free_shipping": free_shipping,
            "shipping_cost": float(shipping.get("cost") or 0.0),
        }
        if seller_meta:
            result.update(seller_meta)
        return result
    except Exception:
        return None


async def fetch_mercadolibre_live(
    client: httpx.AsyncClient,
    query: str,
    limit: int = 10,
    cp: str | None = None,
) -> list[dict]:
    """Consulta productos en vivo desde el catálogo oficial de Mercado Libre y cotiza envío real según el CP."""
    token = await get_meli_token(client)
    if not token:
        return []

    q_clean = query.strip()
    is_ean = q_clean.isdigit() and 8 <= len(q_clean) <= 14

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "SuperVmarket/2.0",
    }

    try:
        products = []
        seen_pids = set()

        if is_ean:
            url = f"https://api.mercadolibre.com/products/search?status=active&site_id=MLA&product_identifier={q_clean}"
            r = await client.get(url, headers=headers, timeout=4.5)
            if r.status_code == 200:
                for p in r.json().get("results", []):
                    pid = p.get("id")
                    if pid and pid not in seen_pids and _is_supermarket_domain(p.get("domain_id")):
                        seen_pids.add(pid)
                        products.append(p)
        else:
            # Lista de consultas a realizar: original + desambiguación para términos de supermercado
            # que en el catálogo global de MeLi se confunden con bazar/automotor (ej: 'coca cola', 'aceite')
            queries_to_try = [q_clean]
            q_lower = q_clean.lower()
            beverage_brands = (
                "coca cola", "coca-cola", "pepsi", "sprite", "fanta", "seven up",
                "7up", "paso de los toros", "aquarius", "manaos", "pritty"
            )
            if any(b in q_lower for b in beverage_brands) and not any(k in q_lower for k in ("gaseosa", "bebida", "refresco")):
                queries_to_try.append(f"gaseosa {q_clean}")
            elif q_lower == "aceite":
                queries_to_try.append("aceite comestible")
            elif q_lower == "shampoo":
                queries_to_try.append("shampoo pelo")
            elif q_lower == "cerveza":
                queries_to_try.append("cerveza lata")
            elif q_lower == "jabon":
                queries_to_try.append("jabon tocador")

            for q_term in queries_to_try:
                q_enc = urllib.parse.quote(q_term)
                url = f"https://api.mercadolibre.com/products/search?status=active&site_id=MLA&q={q_enc}"
                r = await client.get(url, headers=headers, timeout=4.5)
                if r.status_code == 200:
                    for p in r.json().get("results", []):
                        pid = p.get("id")
                        if pid and pid not in seen_pids and _is_supermarket_domain(p.get("domain_id")):
                            seen_pids.add(pid)
                            products.append(p)
                if len(products) >= limit:
                    break

        if not products:
            return []

        # Consultar precios en paralelo para los productos válidos del catálogo de supermercado
        async def _fetch_product_best_item(prod: dict) -> dict | None:
            pid = prod.get("id")
            if not pid or not _is_supermarket_domain(prod.get("domain_id")):
                return None
            it_url = f"https://api.mercadolibre.com/products/{pid}/items"
            try:
                ir = await client.get(it_url, headers=headers, timeout=3.5)
                if ir.status_code == 200:
                    items = ir.json().get("results", [])
                    if items:
                        sids = [it.get("seller_id") for it in items if it.get("seller_id")]
                        await _ensure_seller_reputations(client, token, sids)

                        # 1. Candidatos prioritarios: Full Supermercado / fulfillment oficial / Tiendas Oficiales
                        full_candidates = [
                            it for it in items
                            if float(it.get("price") or 0) > 0 and (
                                (it.get("shipping") or {}).get("logistic_type") == "fulfillment"
                                or "supermarket_eligible" in (it.get("tags") or [])
                                or (it.get("official_store_id") and (it.get("shipping") or {}).get("logistic_type") in ("fulfillment", "drop_off", "cross_docking"))
                            )
                        ]
                        # 2. Si no hay Full o tienda oficial, permitir ofertas activas de vendedores comerciales
                        candidates = full_candidates if full_candidates else [
                            it for it in items
                            if float(it.get("price") or 0) > 0
                        ]
                        if not candidates:
                            # Sin ofertas disponibles en Mercado Libre
                            return None

                        # Priorizar envíos FULL (fulfillment) y dentro de cada tipo siempre menor precio
                        candidates.sort(
                            key=lambda x: (
                                not ((x.get("shipping") or {}).get("logistic_type") == "fulfillment"),
                                float(x.get("price") or 999999),
                            )
                        )
                        best_item = candidates[0]

                        # Armamos las mejores opciones distintas por vendedor para que el usuario elija
                        seen_sellers = set()
                        meli_options = []
                        for it in candidates:
                            sid = it.get("seller_id")
                            if sid in seen_sellers:
                                continue
                            seen_sellers.add(sid)

                            u_info = _SELLER_REP_CACHE.get(sid, {})
                            lvl = u_info.get("level_id") or "unrated"
                            pwr = u_info.get("power_seller_status")
                            nick = u_info.get("nickname") or "Vendedor MeLi"

                            # Nombres amigables para tiendas reconocidas
                            if sid == 252932888:
                                seller_display = "Branca Store (LMG SRL)"
                            elif it.get("official_store_id") or u_info.get("user_type") == "brand":
                                seller_display = f"{nick} (Oficial)"
                            else:
                                seller_display = nick

                            it_id = it.get("item_id", "")
                            clean_id = (
                                f"MLA-{it_id[3:]}"
                                if (it_id.startswith("MLA") and not it_id.startswith("MLA-"))
                                else it_id
                            )
                            raw_direct_link = f"https://articulo.mercadolibre.com.ar/{clean_id}" if it_id else ""
                            direct_link = (
                                decorate_store_url(raw_direct_link, "MercadoLibre", "item")
                                if raw_direct_link
                                else ""
                            )
                            ship = it.get("shipping") or {}
                            is_full = ship.get("logistic_type") == "fulfillment"

                            meli_options.append({
                                "item_id": it_id,
                                "price": float(it.get("price")),
                                "seller_name": seller_display,
                                "reputation": lvl,
                                "power_status": pwr,
                                "is_full": is_full,
                                "free_shipping": ship.get("free_shipping") is True,
                                "shipping_cost": float(ship.get("cost") or 0.0),
                                "link": direct_link,
                            })
                            if len(meli_options) >= 3:
                                break

                        # Ordenar estrictamente las opciones de menor a mayor precio
                        meli_options.sort(key=lambda o: (not o["is_full"], o["price"]))

                        # Metadata del mejor vendedor para la oferta principal
                        best_sid = best_item.get("seller_id")
                        best_u = _SELLER_REP_CACHE.get(best_sid, {})
                        best_ship = best_item.get("shipping") or {}
                        best_nick = best_u.get("nickname") or "Vendedor MeLi"

                        if best_sid == 252932888:
                            primary_seller = "Branca Store (LMG SRL)"
                        elif best_item.get("official_store_id") or best_u.get("user_type") == "brand":
                            primary_seller = f"{best_nick} (Oficial)"
                        else:
                            primary_seller = best_nick

                        exact_shipping_cost = float(best_ship.get("cost") or 0.0)
                        is_free_shipping = best_ship.get("free_shipping") is True

                        # Cotización 100% dinámica en vivo por Código Postal oficial
                        if cp and best_item.get("item_id"):
                            try:
                                it_id = best_item["item_id"]
                                so_url = f"https://api.mercadolibre.com/items/{it_id}/shipping_options?zip_code={cp}"
                                so_r = await client.get(so_url, headers=headers, timeout=2.0)
                                if so_r.status_code == 200:
                                    opts = so_r.json().get("options", [])
                                    if opts:
                                        dyn_cost = float(opts[0].get("cost", 0.0))
                                        exact_shipping_cost = dyn_cost
                                        if dyn_cost == 0:
                                            is_free_shipping = True
                            except Exception:
                                pass

                        seller_meta = {
                            "seller_name": primary_seller,
                            "seller_reputation": best_u.get("level_id") or "unrated",
                            "power_seller_status": best_u.get("power_seller_status"),
                            "free_shipping": is_free_shipping,
                            "shipping_cost": exact_shipping_cost,
                            "meli_options": meli_options,
                        }

                        return parse_meli_product(prod, best_item, seller_meta=seller_meta)
            except Exception:
                pass
            return None

        tasks = [_fetch_product_best_item(p) for p in products[:limit]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if isinstance(r, dict) and r]
    except Exception:
        return []
