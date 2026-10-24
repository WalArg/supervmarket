"""Scraper genérico para tiendas VTEX (Jumbo, Disco, Carrefour, Dia, Vea, etc.).

Crawlea el sitemap para obtener TODO el catálogo y consulta el Catalog System
público por producto. Usa el EAN real como clave de unificación entre tiendas.
"""
import re
import asyncio
import aiohttp
from typing import Optional
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from scrapers.base import BaseScraper, HEADERS
from utils import normalizar_unidad, extraer_unidad_titulo, normalizar_categoria, sanity_precio_unidad


class VtexScraper(BaseScraper):
    def __init__(self, nombre: str, url_base: str, sitemap_url: Optional[str] = None,
                 semaphore_limit: int = 20):
        super().__init__(nombre, url_base, semaphore_limit)
        self.api = f"{url_base}/api/catalog_system/pub/products/search/{{slug}}/p"
        self.sitemap_index = sitemap_url or f"{url_base}/sitemap.xml"

    async def obtener_urls(self, session: aiohttp.ClientSession) -> list[str]:
        print(f"[{self.nombre}] 🗺️  Leyendo sitemap...")
        try:
            async with session.get(self.sitemap_index, headers=HEADERS) as r:
                if r.status != 200:
                    return []
                root = ET.fromstring(await r.read())
            sub_maps = [e.text.strip() for e in root.iter()
                        if "loc" in e.tag and e.text and "product" in e.text]
            urls: list[str] = []
            for chunk_start in range(0, len(sub_maps), 10):
                chunk = sub_maps[chunk_start:chunk_start + 10]
                resps = await asyncio.gather(
                    *(session.get(u, headers=HEADERS) for u in chunk),
                    return_exceptions=True,
                )
                for res in resps:
                    if isinstance(res, aiohttp.ClientResponse) and res.status == 200:
                        try:
                            r_sub = ET.fromstring(await res.read())
                            for e in r_sub.iter():
                                if "loc" in e.tag and e.text and "/p" in e.text:
                                    urls.append(e.text.strip().split("?")[0])
                        except Exception:
                            continue
            unique = list(set(urls))
            print(f"[{self.nombre}] 🎯 {len(unique)} productos detectados.")
            return unique
        except Exception as e:
            print(f"[{self.nombre}] ❌ Error sitemap: {e}")
            return []

    async def procesar(self, session, url, semaforo) -> Optional[dict]:
        async with semaforo:
            try:
                slug = url.split("/p")[0].split("/")[-1]
                if not slug:
                    return None
                async with session.get(self.api.format(slug=slug), headers=HEADERS) as r:
                    if r.status != 200:
                        return None
                    data = await r.json()
                if not data:
                    return None

                prod = data[0]
                sku = prod.get("items", [{}])[0]
                ean = sku.get("ean")
                if not ean:
                    ref = sku.get("referenceId") or [{}]
                    ean = ref[0].get("Value") if ref else None
                if ean:
                    ean = str(ean).replace("~", "").strip()
                if not ean:
                    return None

                comm = sku.get("sellers", [{}])[0].get("commertialOffer", {})
                base_price = comm.get("Price", 0)
                if not base_price:
                    return None
                list_price = comm.get("ListPrice", 0)

                # --- Promos en Teasers (2do al X%, X% off) ---
                best_price = base_price
                teasers = (comm.get("Teasers") or []) + (comm.get("PromotionTeasers") or [])
                for t in teasers:
                    name = str(t.get("<Name>k__BackingField", t.get("Name", ""))).lower()
                    m2 = re.search(r"2do al (\d+)%", name)
                    if m2:
                        d = float(m2.group(1)) / 100
                        best_price = min(best_price, base_price * (2 - d) / 2)
                        continue
                    mo = re.search(r"(\d+)%\s*(off|de descuento)", name)
                    if mo:
                        d = float(mo.group(1)) / 100
                        best_price = min(best_price, base_price * (1 - d))
                precio_venta = round(best_price, 2)

                # --- Unidad / precio por unidad ---
                precio_unidad, unidad = precio_venta, "un"
                cant, u_tit = extraer_unidad_titulo(prod.get("productName", ""))
                if u_tit != "un" and cant > 0:
                    precio_unidad, unidad = precio_venta / cant, u_tit
                p_unidad_norm, unidad_norm = normalizar_unidad(precio_unidad, unidad)
                p_unidad_norm = sanity_precio_unidad(precio_venta, p_unidad_norm, unidad_norm)

                cats = prod.get("categories", []) or []
                cats_str = ", ".join(c.strip("/") for c in cats) if cats else ""
                descuento = 0.0
                if list_price and precio_venta < list_price:
                    descuento = round((1 - precio_venta / list_price) * 100, 1)

                return {
                    "ean": ean,
                    "nombre": prod.get("productName"),
                    "marca": prod.get("brand"),
                    "modelo": "", "tipo": "",
                    "imagen": (sku.get("images", [{}])[0] or {}).get("imageUrl"),
                    "supermercado": self.nombre,
                    "precio_venta": precio_venta,
                    "precio_lista": list_price,
                    "descuento": descuento,
                    "precio_por_unidad": p_unidad_norm,
                    "unidad_medida": unidad_norm,
                    "categorias": normalizar_categoria(cats_str),
                    "stock": comm.get("AvailableQuantity", 0),
                    "itemId": sku.get("itemId"),  # SKU para el carrito
                    "link": url,
                    "fecha": datetime.now(timezone.utc).isoformat(),
                }
            except Exception:
                return None
