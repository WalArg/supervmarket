#!/usr/bin/env python3
"""scripts/daily_scraper.py

Pipeline de Scraping Diario Automatizado para SuperVmarket.
Ejecuta la ingesta sobre el CATÁLOGO TOTAL de las cadenas principales:
- VTEX (Carrefour, Jumbo, Disco, Vea, MasOnline, Dia, On City, Cetrogar, Naldo): Árbol de categorías jerárquico (/tree/3) con paginación de 50 en 50.
- Coto Digital (Oracle Endeca): Barrido de categorías completas de góndola de 50 en 50.
- MercadoLibre: Categorías departamentales oficiales y tiendas oficiales certificadas.

Escribe directamente en Turso Cloud DB (São Paulo / AWS) mediante lotes asíncronos /v2/pipeline.
"""

import os
import sys
import time
import asyncio
import logging
import argparse
from typing import Dict, List, Any, Optional

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
from api._lib.normalization import classify_product_type
from api._lib.catalog_normalizer import classify_canonical_category
from api._lib.parsers import _safe_float, _safe_int, _strip_accents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daily_scraper")

DEFAULT_STORES = [
    # Supermercados
    "Carrefour",
    "Jumbo",
    "Coto",
    "Dia",
    "Masonline",
    "Disco",
    "Vea",
    # Retail / Electro / Marketplaces
    "Fravega",
    "On City",
    "Cetrogar",
    "Naldo",
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

async def run_scraper(
    mode: str = "total",
    stores: Optional[List[str]] = None,
    max_items_per_store: Optional[int] = None,
    batch_size: int = BATCH_SIZE,
):
    """
    Ejecuta el scraper diario.
    mode='total': Barres el catálogo completo mediante category tree / sitemaps (sin semillas arbitrarias).
    mode='seeds': Barres únicamente con palabras clave departamentales (para tests rápidos).
    """
    if not turso.IS_TURSO_CONFIGURED:
        logger.error("TURSO_DATABASE_URL o TURSO_AUTH_TOKEN faltantes. Abortando.")
        return

    active_stores = stores or DEFAULT_STORES
    is_total_mode = (mode == "total")

    logger.info("=================================================================")
    logger.info("Iniciando Daily Scraper en MODO: %s", "CATÁLOGO TOTAL" if is_total_mode else "SEMILLAS")
    logger.info("Tiendas a procesar (%d): %s", len(active_stores), ", ".join(active_stores))
    if max_items_per_store:
        logger.info("Límite máximo por tienda: %d ítems", max_items_per_store)
    else:
        logger.info("Límite por tienda: ILIMITADO (catálogo completo)")
    logger.info("=================================================================")

    total_prods = 0
    total_precios = 0
    start_time = time.time()

    prod_buffer: list = []
    precio_buffer: list = []

    limits = turso.httpx.Limits(max_connections=30, max_keepalive_connections=15, keepalive_expiry=30.0)
    async with turso.httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        for store in active_stores:
            store_start = time.time()
            store_count = 0
            logger.info(">>> Iniciando scraping de %s (modo: %s) <<<", store, mode)

            try:
                if store == "MercadoLibre":
                    # MercadoLibre procesa categorías principales de consumo masivo y tecnología
                    from api._lib.mercadolibre import fetch_mercadolibre_live
                    search_queries = (
                        DEPARTMENTAL_SEEDS[:20] if not is_total_mode
                        else ["alimentos y bebidas", "lacteos y frescos", "limpieza del hogar", "cuidado personal", "bebidas", "smartphones celulares", "smart tv televisores"]
                    )
                    for query in search_queries:
                        try:
                            items = await fetch_mercadolibre_live(client, query, limit=25)
                            for m in items:
                                p_val = float(m.get("precio") or m.get("precio_venta") or 0.0)
                                if p_val <= 0:
                                    continue
                                ean_val = str(m.get("ean") or f"MELI-{m.get('id') or abs(hash(m.get('title','')))}")
                                nom_val = m.get("title") or m.get("nombre") or ""
                                marca_val = m.get("marca") or "MercadoLibre"
                                img_val = m.get("imagen") or m.get("image") or ""
                                link_val = m.get("link") or m.get("url") or ""
                                cats_val = m.get("categoria") or query
                                cat_norm = classify_canonical_category(nom_val, marca_val, cats_val, "marketplace")
                                p_type = classify_product_type(cats_val, "marketplace")
                                search_txt = _strip_accents(f"{nom_val} {marca_val} {ean_val} MercadoLibre {cats_val}").lower()
                                now_str = time.strftime("%Y-%m-%d %H:%M:%S")

                                prod_buffer.append((
                                    ean_val, nom_val, marca_val, "", p_type, img_val,
                                    "MercadoLibre", cats_val, cat_norm, now_str, search_txt
                                ))
                                precio_buffer.append((
                                    ean_val, "MercadoLibre", p_val, p_val, 0.0, None, "un",
                                    1, str(m.get("id") or ""), link_val, now_str,
                                    None, None, 1, p_val, 0, str(m.get("seller_name") or "1"), "marketplace"
                                ))
                                store_count += 1
                                if len(prod_buffer) >= batch_size:
                                    await flush_buffer(client, prod_buffer, precio_buffer)
                        except Exception as e:
                            logger.warning("Error en MeLi query %s: %s", query, e)
                else:
                    # Tiendas VTEX, Coto y Shopify:
                    # En modo total (seeds_only=False), recorren el árbol de categorías nativo
                    async for item in harvest_store(
                        store_key=store,
                        categories_or_seeds=DEPARTMENTAL_SEEDS[:30] if not is_total_mode else None,
                        max_items=max_items_per_store,
                        seeds_only=not is_total_mode,
                        include_sitemap=is_total_mode,
                    ):
                        p_val = _safe_float(item.get("price_raw"), 0.0)
                        if p_val <= 0:
                            continue

                        title = item.get("title_raw") or ""
                        brand = item.get("brand_raw") or ""
                        ext_id = str(item.get("external_id") or "")
                        ean_raw = str(item.get("ean_raw") or "")
                        ean_cand = resolve_product_ean(store, ext_id, ean_raw)
                        if not ean_cand:
                            continue

                        link = item.get("link_raw") or ""
                        img = item.get("image_raw") or ""
                        cats = item.get("categories_raw") or ""
                        list_price = _safe_float(item.get("list_price_raw"), p_val)
                        disc = round((1.0 - p_val / list_price) * 100.0, 1) if list_price > p_val else 0.0
                        search_txt = _strip_accents(f"{title} {brand} {ean_cand} {store} {cats}").lower()
                        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

                        store_type = classify_product_type(cats, "supermarket")
                        cat_norm = classify_canonical_category(title, brand, cats, store_type)

                        prod_buffer.append((
                            ean_cand, title, brand, "", store_type, img,
                            store, cats, cat_norm, now_str, search_txt
                        ))
                        precio_buffer.append((
                            ean_cand, store, p_val, list_price, disc, None, "un",
                            1, ext_id, link, now_str,
                            f"{int(disc)}% OFF" if disc >= 5 else None, "DIRECT" if disc >= 5 else None,
                            1, p_val, 0, str(item.get("seller_id_raw") or "1"), store_type
                        ))
                        store_count += 1

                        if len(prod_buffer) >= batch_size:
                            await flush_buffer(client, prod_buffer, precio_buffer)

                # Vaciar remanente de la tienda
                if prod_buffer or precio_buffer:
                    await flush_buffer(client, prod_buffer, precio_buffer)

                total_prods += store_count
                total_precios += store_count
                logger.info("Tienda %s finalizada: %d productos en %.1fs", store, store_count, time.time() - store_start)

            except Exception as e:
                logger.error("Error durante scraping de %s: %s", store, e, exc_info=True)

    duration = time.time() - start_time
    logger.info("=================================================================")
    logger.info("Daily Scraper finalizado con éxito en %.1f segundos.", duration)
    logger.info("Total ítems procesados: %d productos / %d precios.", total_prods, total_precios)
    logger.info("=================================================================")

def main():
    parser = argparse.ArgumentParser(description="SuperVmarket Daily Scraper")
    parser.add_argument(
        "--mode",
        choices=["total", "seeds"],
        default="total",
        help="Modo de ejecución: 'total' (catálogo completo por árbol de categorías) o 'seeds' (muestreo rápido)",
    )
    parser.add_argument(
        "--stores",
        nargs="+",
        help="Tiendas específicas a scrapear (ej: --stores Carrefour Jumbo Coto)",
    )
    parser.add_argument(
        "--max-items-per-store",
        type=int,
        default=None,
        help="Límite máximo de productos por tienda (por defecto ilimitado / total)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help="Tamaño de lote para Turso pipeline (defecto: 80)",
    )
    args = parser.parse_args()

    asyncio.run(
        run_scraper(
            mode=args.mode,
            stores=args.stores,
            max_items_per_store=args.max_items_per_store,
            batch_size=args.batch_size,
        )
    )

if __name__ == "__main__":
    main()
