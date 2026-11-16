#!/usr/bin/env python3
"""scripts/daily_scraper.py

Pipeline de Scraping Diario Automatizado para SuperVmarket.
Ejecuta la ingesta de las cadenas principales (Jumbo, Carrefour, Coto, Dia, MasOnline, MercadoLibre)
sobre el catálogo general nacional (sin sesgo de sucursal oculta).
Escribe directamente en Turso / LibSQL en la nube mediante lotes asíncronos.
"""

import os
import sys
import time
import asyncio
import logging
from typing import Dict, List, Any

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib import turso
from api._lib.harvester import (
    DEPARTMENTAL_SEEDS,
    HarvesterItem,
    harvest_store,
    resolve_product_ean,
)
from api._lib.normalization import extract_canonical_model
from api._lib.parsers import _safe_float, _safe_int, _strip_accents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daily_scraper")

STORES_TO_HARVEST = [
    # Supermercados
    "Carrefour",
    "Jumbo",
    "Coto",
    "Dia",
    "Masonline",
    "Disco",
    "Vea",
    # Electro / Marketplaces
    "Fravega",
    "On City",
    "Provincia Compras",
    "MercadoLibre",
]

BATCH_SIZE = 80

def _to_turso_arg(val: Any) -> dict:
    if val is None:
        return {"type": "null"}
    elif isinstance(val, bool):
        return {"type": "integer", "value": "1" if val else "0"}
    elif isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    elif isinstance(val, float):
        return {"type": "float", "value": val}
    else:
        return {"type": "text", "value": str(val)}

async def send_turso_batch(client: turso.httpx.AsyncClient, statements: list, retries: int = 3) -> bool:
    if not turso.IS_TURSO_CONFIGURED:
        logger.error("Turso no está configurado. Definir TURSO_DATABASE_URL y TURSO_AUTH_TOKEN.")
        return False
    pipeline_url = f"{turso.TURSO_HTTP_URL.rstrip('/')}/v2/pipeline"
    payload = {
        "requests": [{"type": "execute", "stmt": s} for s in statements] + [{"type": "close"}]
    }
    headers = {
        "Authorization": f"Bearer {turso._TURSO_TOKEN}",
        "Content-Type": "application/json"
    }
    for attempt in range(retries):
        try:
            resp = await client.post(pipeline_url, json=payload, headers=headers, timeout=25.0)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results and results[0].get("type") == "ok":
                    return True
        except Exception as e:
            if attempt == retries - 1:
                logger.error("Fallo al enviar lote a Turso: %s", e)
            await asyncio.sleep(1.0 * (attempt + 1))
    return False

async def flush_buffer(client: turso.httpx.AsyncClient, prod_buffer: list, precio_buffer: list):
    if prod_buffer:
        sql_prod = (
            "INSERT OR REPLACE INTO productos (ean, nombre, marca, modelo, tipo, imagen, "
            "supermercado_origen, categorias, categoria_normalizada, actualizado, search_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        stmts = [{"sql": sql_prod, "args": [_to_turso_arg(v) for v in r]} for r in prod_buffer]
        await send_turso_batch(client, stmts)
        prod_buffer.clear()

    if precio_buffer:
        sql_pr = (
            "INSERT OR REPLACE INTO precios (ean, supermercado, precio_venta, precio_lista, "
            "descuento, precio_por_unidad, unidad_medida, stock, internal_id, link, fecha, "
            "promo_etiqueta, promo_tipo, promo_min_qty, precio_promo_unit, requiere_club, "
            "seller_id, store_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        stmts = [{"sql": sql_pr, "args": [_to_turso_arg(v) for v in r]} for r in precio_buffer]
        await send_turso_batch(client, stmts)
        precio_buffer.clear()

async def run_scraper(seeds: List[str] = None, max_items_per_store: int = 500):
    if not turso.IS_TURSO_CONFIGURED:
        logger.error("TURSO_DATABASE_URL o TURSO_AUTH_TOKEN faltantes. Abortando.")
        return

    active_seeds = seeds or DEPARTMENTAL_SEEDS[:30]
    logger.info("Iniciando Daily Scraper para %d tiendas con %d semillas...", len(STORES_TO_HARVEST), len(active_seeds))

    total_prods = 0
    total_precios = 0
    start_time = time.time()

    prod_buffer: list = []
    precio_buffer: list = []

    limits = turso.httpx.Limits(max_connections=30, max_keepalive_connections=15, keepalive_expiry=30.0)
    async with turso.httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        for store in STORES_TO_HARVEST:
            store_start = time.time()
            store_count = 0
            logger.info("--- Scrapeando %s ---", store)

            try:
                # MercadoLibre maneja su propia ingesta directa
                if store == "MercadoLibre":
                    from api._lib.mercadolibre import fetch_mercadolibre_live
                    for seed in active_seeds[:15]:
                        try:
                            items = await fetch_mercadolibre_live(client, seed, limit=12)
                            for m in items:
                                p_val = float(m.get("precio") or m.get("precio_venta") or 0.0)
                                if p_val <= 0:
                                    continue
                                ean_val = str(m.get("ean") or f"MELI-{m.get('id') or abs(hash(m.get('title','')))}")
                                nom_val = m.get("title") or m.get("nombre") or ""
                                marca_val = m.get("marca") or "MercadoLibre"
                                img_val = m.get("imagen") or m.get("image") or ""
                                link_val = m.get("link") or m.get("url") or ""
                                search_txt = _strip_accents(f"{nom_val} {marca_val} {ean_val} MercadoLibre").lower()

                                prod_buffer.append((
                                    ean_val, nom_val, marca_val, "", "marketplace", img_val,
                                    "MercadoLibre", "", "general", time.strftime("%Y-%m-%d %H:%M:%S"), search_txt
                                ))
                                precio_buffer.append((
                                    ean_val, "MercadoLibre", p_val, p_val, 0.0, None, "un",
                                    1, str(m.get("id") or ""), link_val, time.strftime("%Y-%m-%d %H:%M:%S"),
                                    None, None, 1, p_val, 0, str(m.get("seller_name") or "1"), "marketplace"
                                ))
                                store_count += 1
                                if len(prod_buffer) >= BATCH_SIZE:
                                    await flush_buffer(client, prod_buffer, precio_buffer)
                        except Exception as e:
                            logger.warning("Error en MeLi seed %s: %s", seed, e)
                else:
                    async for item in harvest_store(
                        store_key=store,
                        categories_or_seeds=active_seeds,
                        max_items=max_items_per_store,
                        seeds_only=True,
                        include_sitemap=False,
                    ):
                        p_val = _safe_float(item.get("price_raw"), 0.0)
                        if p_val <= 0:
                            continue

                        title = item.get("title_raw") or ""
                        brand = item.get("brand_raw") or ""
                        ean_cand = resolve_product_ean(item)
                        if not ean_cand:
                            continue

                        link = item.get("link_raw") or ""
                        img = item.get("image_raw") or ""
                        cats = item.get("categories_raw") or ""
                        list_price = _safe_float(item.get("list_price_raw"), p_val)
                        disc = round((1.0 - p_val / list_price) * 100.0, 1) if list_price > p_val else 0.0
                        search_txt = _strip_accents(f"{title} {brand} {ean_cand} {store} {cats}").lower()

                        prod_buffer.append((
                            ean_cand, title, brand, "", "supermarket", img,
                            store, cats, "almacen", time.strftime("%Y-%m-%d %H:%M:%S"), search_txt
                        ))
                        precio_buffer.append((
                            ean_cand, store, p_val, list_price, disc, None, "un",
                            1, str(item.get("external_id") or ""), link, time.strftime("%Y-%m-%d %H:%M:%S"),
                            f"{int(disc)}% OFF" if disc >= 5 else None, "DIRECT" if disc >= 5 else None,
                            1, p_val, 0, str(item.get("seller_id_raw") or "1"), "supermarket"
                        ))
                        store_count += 1

                        if len(prod_buffer) >= BATCH_SIZE:
                            await flush_buffer(client, prod_buffer, precio_buffer)

                # Vaciar remanente de la tienda
                if prod_buffer or precio_buffer:
                    await flush_buffer(client, prod_buffer, precio_buffer)

                total_prods += store_count
                total_precios += store_count
                logger.info("Tienda %s finalizada: %d productos en %.1fs", store, store_count, time.time() - store_start)

            except Exception as e:
                logger.error("Error durante scraping de %s: %s", store, e)

    duration = time.time() - start_time
    logger.info("==========================================")
    logger.info("Daily Scraper finalizado con éxito en %.1f segundos.", duration)
    logger.info("Total ítems procesados: %d productos / %d precios.", total_prods, total_precios)
    logger.info("==========================================")

if __name__ == "__main__":
    asyncio.run(run_scraper())
