"""Scraper de Coto (Oracle Endeca, ?format=json).

Audita `product.dtoDescuentos` contrastado con los dumps reales de Coto Digital:
- Corrige el bug de dividir por 100 precios que no tienen centavos.
- Distingue descuentos abiertos a todo público (`imagenDescuento: " "`) de descuentos exclusivos
  de **Comunidad Coto** (`imagenDescuento` con `comunidad.png`) o medios de pago.
- Soporta ofertas escalonadas (`2da al X%`, `NxM`).
"""
import io
import gzip
import re
import json
import aiohttp
from typing import Optional
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from base_scraper import BaseScraper, HEADERS
from utils import normalizar_unidad, extraer_unidad_titulo, normalizar_categoria, sanity_precio_unidad


def _parse_ars_price(raw_txt: str) -> Optional[float]:
    """Convierte '$35704.50', '$1.290,00' o '$4098.41c/u' al float exacto en ARS."""
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
    """Evalúa el array `product.dtoDescuentos` de Coto separando precio público vs Comunidad Coto / cantidad."""
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
        # 1. ¿Es oferta por cantidad (2da unidad / NxM)?
        m_2da = re.search(r"2d[ao].*?(\d+)\s*%|(\d+)\s*%.*?2d[ao]", low_txt)
        m_nxm = re.search(r"\b([2346])\s*x\s*([12345])\b", low_txt)

        if m_2da:
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

        # 2. Descuento en 1 unidad (Abierto o Comunidad Coto)
        if p_dto and p_dto < precio_lista:
            pct_calc = int(round((1.0 - p_dto / precio_lista) * 100))
            if not is_comunidad:
                # Descuento abierto a todo público para 1 unidad
                res["precio_venta"] = p_dto
                if p_dto <= res["precio_promo_unit"]:
                    res["precio_promo_unit"] = p_dto
                    res["promo_etiqueta"] = f"{pct_calc}% OFF"
                    res["promo_tipo"] = "DIRECT"
                    res["promo_min_qty"] = 1
                    res["requiere_club"] = False
            else:
                # Descuento exclusivo Comunidad Coto (puede ser único o adicional "+15%" sobre el abierto)
                if p_dto < res["precio_promo_unit"]:
                    res["precio_promo_unit"] = p_dto
                    res["promo_etiqueta"] = f"{pct_calc}% Comunidad Coto"
                    res["promo_tipo"] = "CLUB_PCT"
                    res["promo_min_qty"] = 1
                    res["requiere_club"] = True

    return res


def parse_coto_record(data: dict, item_id: str = "", url: str = "") -> Optional[dict]:
    """Convierte un registro Endeca de Coto Digital (individual o de lote) en diccionario normalizado."""
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

    try:
        p_list = float((attrs.get("sku.activePrice") or ["0"])[0] or 0)
    except Exception:
        p_list = 0.0
    if p_list <= 0:
        return None

    promo = parse_coto_discounts(p_list, attrs.get("product.dtoDescuentos", []))
    p_venta = promo["precio_venta"]

    if not item_id:
        rec_id = (attrs.get("record.id") or attrs.get("product.repositoryId") or [""])[0]
        m = re.search(r"(\d+)", str(rec_id))
        item_id = m.group(1) if m else str(rec_id)

    ean = (attrs.get("product.eanPrincipal") or [""])[0].strip() or f"COTO-{item_id}"

    precio_unidad, unidad = p_venta, "un"
    cant, u_tit = extraer_unidad_titulo(nombre)
    if cant > 0 and (u_tit != "un" or cant > 1):
        precio_unidad, unidad = p_venta / cant, u_tit
    p_unidad_norm, unidad_norm = normalizar_unidad(precio_unidad, unidad)
    p_unidad_norm = sanity_precio_unidad(p_venta, p_unidad_norm, unidad_norm)

    cats = ((attrs.get("parentCategory.displayName") or [""])[0]
            or (attrs.get("product.category") or [""])[0])
    descuento = round((1.0 - p_venta / p_list) * 100.0, 1) if p_venta < p_list else 0.0

    if not url:
        rec_state = (record.get("detailsAction") or {}).get("recordState") or ""
        if rec_state:
            url = f"https://www.cotodigital.com.ar/sitios/cdigi/productos{rec_state.split('?')[0]}"
    clean_url = url.split("?")[0] if url else f"https://www.cotodigital.com.ar/sitios/cdigi/productos/_/R-{item_id}"

    return {
        "ean": ean,
        "nombre": nombre,
        "marca": marca,
        "modelo": "",
        "tipo": "",
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
        "categorias": normalizar_categoria(cats),
        "stock": 1,
        "itemId": str(item_id),
        "link": clean_url,
        "fecha": datetime.now(timezone.utc).isoformat(),
    }


class CotoScraper(BaseScraper):
    """Descarga el catálogo de Coto Digital por lotes de 200 productos/request (200x más rápido que sitemap)."""

    def __init__(self, semaphore_limit: int = 10):
        super().__init__("Coto", "https://www.cotodigital.com.ar", semaphore_limit)
        self.batch_url = "https://www.cotodigital.com.ar/sitios/cdigi/categoria?format=json&No={offset}&Nrpp=200"

    async def obtener_urls(self, session: aiohttp.ClientSession) -> list[int]:
        return list(range(0, 6000, 200))

    async def procesar(self, session: aiohttp.ClientSession, offset: int, semaforo) -> list[dict]:
        async with semaforo:
            try:
                url = self.batch_url.format(offset=offset)
                async with session.get(url, headers=HEADERS) as r:
                    if r.status != 200:
                        return []
                    data = await r.json(content_type=None)
                out = []
                for m in data.get("contents", [{}])[0].get("Main", []):
                    for c in m.get("contents", []):
                        for rec in c.get("records", []):
                            parsed = parse_coto_record(rec)
                            if parsed:
                                out.append(parsed)
                return out
            except Exception:
                return []

    async def correr(self, limit: Optional[int] = None) -> list[dict]:
        import asyncio
        max_items = limit or 4000
        offsets = list(range(0, max_items, 200))
        print(f"[{self.nombre}] Descargando hasta {max_items} productos en {len(offsets)} lotes de 200...", flush=True)
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=12, sock_read=25)
        connector = aiohttp.TCPConnector(limit=self.semaphore_limit * 2, ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            semaforo = asyncio.Semaphore(self.semaphore_limit)
            batches = await asyncio.gather(*(self.procesar(session, off, semaforo) for off in offsets))
        by_ean: dict[str, dict] = {}
        for b in batches:
            for p in b:
                by_ean[p["ean"]] = p
                if limit and len(by_ean) >= limit:
                    break
            if limit and len(by_ean) >= limit:
                break
        result = list(by_ean.values())
        print(f"[{self.nombre}] OK {len(result)} productos unicos descargados.", flush=True)
        return result
