"""Scraper genérico para tiendas VTEX (Jumbo, Disco, Vea, Carrefour, Dia, Masonline, Farmacity, etc.).

Verificación estricta contra fuentes reales:
1. NUNCA usa `productClusters` para inferir descuentos porque en VTEX quedan colecciones históricas
   vencidas (ej. "AÑO 2022", "20 A 28 MAYO", "Semana 14") que ya no existen en la página real.
2. Solo toma ofertas 100% vigentes hoy en el motor de precios de VTEX:
   - Descuento directo activo en 1 unidad: `commertialOffer.Price < commertialOffer.ListPrice`
     (descartando el falso ListPrice de Cencosud Jumbo/Disco/Vea que trae el precio sin IVA * 100).
   - Promociones por cantidad / tarjetas vigentes hoy: `commertialOffer.PromotionTeasers` y `Teasers`.
3. Las promociones ocultas de carrito en Cencosud/Carrefour se validan en vivo mediante
   `/api/checkout/pub/orderForms/simulation?sc=XX` en `api/_lib/carts.py`.
"""
import re
import asyncio
import random
import aiohttp
from typing import Optional
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from base_scraper import BaseScraper, HEADERS
from utils import normalizar_unidad, extraer_unidad_titulo, normalizar_categoria, sanity_precio_unidad

CLUB_KEYWORDS = (
    "club dia", "mi carrefour", "tarjeta carrefour", "cencopay", "cencosud",
    "mas club", "más club", "tu farmacity", "comunidad", "bsf", "banco",
    "anses", "jubilado", "modo", "bna", "cuenta dni", "mp ", "mercadopago",
)


def _has_bin_restriction(teaser: dict) -> bool:
    """Detecta si un Teaser de VTEX exige BINs de tarjeta bancaria (ej: Tarjeta Carrefour)."""
    conds = teaser.get("Conditions") or teaser.get("<Conditions>k__BackingField") or {}
    params = conds.get("Parameters") or conds.get("<Parameters>k__BackingField") or []
    for p in params:
        p_name = str(p.get("Name") or p.get("<Name>k__BackingField") or "")
        if "RestrictionsBins" in p_name and (p.get("Value") or p.get("<Value>k__BackingField")):
            return True
    return False


def _parse_active_teaser(text: str, base_price: float, list_price: float,
                         force_club: bool = False) -> Optional[dict]:
    """Extrae una regla estructurada únicamente desde un Teaser activo de VTEX."""
    if not text:
        return None
    clean = text.strip()
    low = clean.lower()
    is_club = force_club or any(k in low for k in CLUB_KEYWORDS)

    # 1. Promociones "2do al X%" / "2da unidad al X%"
    m_2do = re.search(
        r"(?:2d[oa](?:\s+unidad)?\s+al\s*(\d+)\s*%)|(?:(\d+)\s*%\s*(?:off\s+)?.*?(?:2da|segunda)\s+unidad)",
        low,
    )
    if m_2do:
        pct_val = int(m_2do.group(1) or m_2do.group(2))
        if 10 <= pct_val <= 95:
            d = pct_val / 100.0
            eff_unit = round(base_price * (2.0 - d) / 2.0, 2)
            label = f"2do al {pct_val}%" + (" (Club/Tarjeta)" if is_club else "")
            return {
                "promo_etiqueta": label,
                "promo_tipo": "CLUB_PCT" if is_club else "BULK_PCT",
                "promo_min_qty": 2,
                "precio_promo_unit": eff_unit,
                "requiere_club": is_club,
            }

    # 2. Promociones NxM ("2x1", "3x2", "4x3", "6x4", "6x5")
    m_nxm = re.search(r"\b([2346])\s*x\s*([12345])\b", low)
    if m_nxm:
        n, m = int(m_nxm.group(1)), int(m_nxm.group(2))
        if n > m > 0:
            eff_unit = round(base_price * (m / n), 2)
            label = f"{n}x{m}" + (" (Tu Farmacity/Club)" if is_club else "")
            return {
                "promo_etiqueta": label,
                "promo_tipo": "CLUB_PCT" if is_club else "NXM",
                "promo_min_qty": n,
                "precio_promo_unit": eff_unit,
                "requiere_club": is_club,
            }

    # 3. Descuento porcentual en Teaser activo (ej: "Tarjeta Carrefour 15%")
    m_pct = re.search(r"(\d{1,2})\s*%", low)
    if m_pct:
        pct_val = int(m_pct.group(1))
        if 5 <= pct_val <= 70:
            eff_unit = round(base_price * (1.0 - pct_val / 100.0), 2)
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
                return {
                    "promo_etiqueta": f"{pct_val}% OFF",
                    "promo_tipo": "DIRECT",
                    "promo_min_qty": 1,
                    "precio_promo_unit": eff_unit,
                    "requiere_club": False,
                }

    return None


def parse_vtex_product(prod: dict, store_name: str, fallback_url: str = "") -> Optional[dict]:
    """Convierte el JSON de un producto VTEX en nuestro diccionario normalizado con ofertas 100% reales.
    Descarta estrictamente cualquier producto sin stock disponible (`AvailableQuantity <= 0`).
    """
    if not prod or not isinstance(prod, dict):
        return None
    items = prod.get("items") or []
    if not items:
        return None

    # Elegir el primer SKU que tenga stock > 0 y precio > 0
    sku = None
    comm = None
    for candidate_sku in items:
        sellers = candidate_sku.get("sellers") or []
        if not sellers:
            continue
        c_offer = sellers[0].get("commertialOffer") or {}
        avail = int(c_offer.get("AvailableQuantity") or 0)
        price = float(c_offer.get("Price") or 0)
        if avail > 0 and price > 0:
            sku = candidate_sku
            comm = c_offer
            break

    # Si ningún SKU tiene stock real disponible, no se muestra en la página
    if not sku or not comm:
        return None

    ean = sku.get("ean")
    if not ean:
        ref = sku.get("referenceId") or [{}]
        ean = ref[0].get("Value") if ref else None
    if not ean:
        ean_spec = prod.get("EAN")
        if isinstance(ean_spec, list) and ean_spec:
            ean = ean_spec[0]
    ean = str(ean or "").replace("~", "").strip()
    if not ean:
        return None

    base_price = float(comm.get("Price") or 0)
    if base_price <= 0:
        return None

    raw_list_price = float(comm.get("ListPrice") or base_price)
    # En Cencosud (Jumbo, Disco, Vea), ListPrice trae el Precio Sin Impuestos * 100 (~82x el Price real).
    if raw_list_price > base_price * 4.0 or raw_list_price < base_price:
        list_price = base_price
    else:
        list_price = raw_list_price

    precio_venta = round(base_price, 2)
    descuento = round((1.0 - precio_venta / list_price) * 100.0, 1) if list_price > precio_venta else 0.0

    # 1. Si Price < ListPrice real, ya tiene un descuento directo real aplicado en el precio de 1 unidad
    best_promo = {
        "promo_etiqueta": f"{int(round(descuento))}% OFF" if descuento >= 3 else None,
        "promo_tipo": "DIRECT" if descuento >= 3 else None,
        "promo_min_qty": 1,
        "precio_promo_unit": precio_venta,
        "requiere_club": False,
    }

    # 2. Revisar únicamente Teasers / PromotionTeasers activos del motor de promociones de VTEX
    teasers = (comm.get("PromotionTeasers") or []) + (comm.get("Teasers") or [])
    for t in teasers:
        t_name = str(t.get("Name") or t.get("<Name>k__BackingField") or "").strip()
        if not t_name:
            continue
        cand = _parse_active_teaser(t_name, precio_venta, list_price, force_club=_has_bin_restriction(t))
        if not cand:
            continue
        # Si ya hay un descuento directo abierto (ej: 35% OFF en Carrefour) y el Teaser es solo "Tarjeta Carrefour 15%",
        # conservamos el descuento abierto como principal.
        if best_promo["promo_tipo"] == "DIRECT" and cand["requiere_club"]:
            continue
        # Priorizar promociones abiertas (no club) sobre promociones con restricción de club/tarjeta
        if (best_promo["promo_etiqueta"] is None
                or (best_promo["requiere_club"] and not cand["requiere_club"])
                or (cand["requiere_club"] == best_promo["requiere_club"]
                    and cand["precio_promo_unit"] < best_promo["precio_promo_unit"])):
            best_promo = cand

    # --- Unidad / precio por unidad ---
    nombre = prod.get("productName") or sku.get("nameComplete") or sku.get("name") or ""
    precio_unidad, unidad = precio_venta, "un"
    cant, u_tit = extraer_unidad_titulo(nombre)
    if cant > 0 and (u_tit != "un" or cant > 1):
        precio_unidad, unidad = precio_venta / cant, u_tit
    p_unidad_norm, unidad_norm = normalizar_unidad(precio_unidad, unidad)
    p_unidad_norm = sanity_precio_unidad(precio_venta, p_unidad_norm, unidad_norm)

    cats = prod.get("categories") or []
    cats_str = ", ".join(c.strip("/") for c in cats) if cats else ""
    link = prod.get("link") or fallback_url
    if link and link.startswith("/"):
        link = f"https://www.{store_name.lower()}.com.ar{link}"

    return {
        "ean": ean,
        "nombre": nombre,
        "marca": prod.get("brand") or "Genérico",
        "modelo": "",
        "tipo": "",
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
        "stock": int(comm.get("AvailableQuantity") or 0),
        "itemId": str(sku.get("itemId") or ""),
        "link": link,
        "fecha": datetime.now(timezone.utc).isoformat(),
    }


SALES_CHANNELS = {
    "Jumbo": 32,
    "Disco": 33,
    "Vea": 34,
    "Farmacity": 4,
}

SKIP_DEPT_KEYWORDS = (
    "electro", "tecnolog", "mueble", "colchon", "automotor", "rodado",
    "jard", "aire libre", "textil", "indumentaria", "moda", "juguete",
    "librer", "ferreter", "pintura", "construcci", "test", "integracion",
    "mercadolibre", "(old)", "tiempo libre", "deporte", "bazar",
)


class VtexScraper(BaseScraper):
    """Descarga el catálogo VTEX en lotes de 50 productos por request (_from/_to) por categoría.

    Esto reduce el tiempo de descarga 50x respecto a consultar URL por URL del sitemap,
    y evita traer 250.000 URLs históricas o de Marketplace (electro/colchones/muebles).
    """

    def __init__(self, nombre: str, url_base: str, sitemap_url: Optional[str] = None,
                 semaphore_limit: int = 12):
        super().__init__(nombre, url_base, semaphore_limit)
        self.sc = SALES_CHANNELS.get(nombre)
        self.sc_qs = f"&sc={self.sc}" if self.sc else ""
        self.tree_url = f"{url_base}/api/catalog_system/pub/category/tree/3"
        self.search_url = f"{url_base}/api/catalog_system/pub/products/search"
        self.sitemap_index = sitemap_url or f"{url_base}/sitemap.xml"

    async def obtener_urls(self, session: aiohttp.ClientSession) -> list[str]:
        """Obtiene los filtros de categorías de consumo masivo / farmacia para paginar de a 50."""
        try:
            async with session.get(self.tree_url, headers=HEADERS) as r:
                if r.status != 200:
                    return [""]
                tree = await r.json(content_type=None)
            if not isinstance(tree, list) or not tree:
                return [""]

            cat_filters: list[str] = []
            for dept in tree:
                d_id = dept.get("id")
                d_name = str(dept.get("name") or "").lower()
                if not d_id or any(k in d_name for k in SKIP_DEPT_KEYWORDS):
                    continue
                children = dept.get("children") or []
                if children and len(children) <= 25:
                    for ch in children:
                        c_id = ch.get("id")
                        c_name = str(ch.get("name") or "").lower()
                        if c_id and not any(k in c_name for k in SKIP_DEPT_KEYWORDS):
                            cat_filters.append(f"fq=C:/{d_id}/{c_id}/")
                else:
                    cat_filters.append(f"fq=C:/{d_id}/")
            return cat_filters if cat_filters else [""]
        except Exception:
            return [""]

    async def _fetch_page(self, session: aiohttp.ClientSession, fq: str, start: int,
                          semaforo: asyncio.Semaphore) -> list[dict]:
        end = start + 49
        qs = f"{fq}&_from={start}&_to={end}{self.sc_qs}" if fq else f"_from={start}&_to={end}{self.sc_qs}"
        url = f"{self.search_url}?{qs}"
        async with semaforo:
            for attempt in range(3):
                try:
                    async with session.get(url, headers=HEADERS) as r:
                        if r.status in (200, 206):
                            data = await r.json(content_type=None)
                            if not isinstance(data, list):
                                return []
                            out = []
                            for raw_prod in data:
                                parsed = parse_vtex_product(raw_prod, self.nombre)
                                if parsed:
                                    out.append(parsed)
                            return out
                        if r.status in (429, 500, 502, 503, 504):
                            await asyncio.sleep((1.5 ** attempt) + random.uniform(0.1, 0.4))
                            continue
                        return []
                except Exception:
                    if attempt == 2:
                        return []
                    await asyncio.sleep(0.5)
            return []

    async def procesar(self, session: aiohttp.ClientSession, url: str, semaforo: asyncio.Semaphore) -> Optional[dict]:
        return None

    async def correr(self, limit: Optional[int] = None) -> list[dict]:
        max_target = limit or 3500
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=12, sock_read=25)
        connector = aiohttp.TCPConnector(limit=self.semaphore_limit * 2, ssl=False)
        by_ean: dict[str, dict] = {}

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            cat_filters = await self.obtener_urls(session)
            semaforo = asyncio.Semaphore(self.semaphore_limit)
            # Paginamos en rondas por categoría (primero página 0..49 de cada subcategoría, luego 50..99, etc.)
            # para tener variedad completa de todo el supermercado.
            max_pages_per_cat = max(1, min(15, (max_target // max(len(cat_filters) * 35, 1)) + 2))
            print(
                f"[{self.nombre}] Explorando {len(cat_filters)} categorias en lotes de 50 "
                f"(meta ~{max_target} productos)...",
                flush=True,
            )
            active_cats = list(cat_filters)
            for page_idx in range(max_pages_per_cat):
                if not active_cats or len(by_ean) >= max_target:
                    break
                start = page_idx * 50
                if start >= 2500:
                    break
                tasks = [self._fetch_page(session, fq, start, semaforo) for fq in active_cats]
                results = await asyncio.gather(*tasks)
                next_active = []
                for fq, batch in zip(active_cats, results):
                    for prod in batch:
                        by_ean[prod["ean"]] = prod
                    # Si devolvió al menos 40 productos válidos, probablemente hay otra página
                    if len(batch) >= 35:
                        next_active.append(fq)
                active_cats = next_active
                print(f"[{self.nombre}] {len(by_ean)} productos unicos acumulados...", flush=True)
                if len(by_ean) >= max_target:
                    break

        final_list = list(by_ean.values())
        promos = sum(1 for p in final_list if p.get("promo_etiqueta"))
        print(f"[{self.nombre}] OK {len(final_list)} productos ({promos} con oferta).", flush=True)
        return final_list
