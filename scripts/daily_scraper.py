#!/usr/bin/env python3
"""scripts/daily_scraper.py

Pipeline de Scraping Diario Automatizado para SuperVmarket.
Arquitectura de Alta Velocidad por Lotes Activos (Target: Catálogo Completo en <15 minutos):
1. Ingesta masiva por Árbol de Categorías Jerárquico (/tree/3) en lotes de 50 productos activos por petición
   (Carrefour, Jumbo, Disco, Vea, MasOnline, Dia). Cero URLs muertas ni obsoletas.
2. Coto Digital: Barrido directo de catálogo Endeca en lotes de 50 ítems.
3. Mercado Libre: Tiendas oficiales certificadas y categorías de consumo masivo / tecnología.
4. Ingesta por streaming directo en lotes (/v2/pipeline) hacia Turso Cloud DB (São Paulo / AWS).
5. Notificaciones push instantáneas a ntfy.sh, Discord o Telegram con reporte completo de productos actualizados.
"""

import os
import sys
import time
import asyncio
import logging
import argparse
import signal
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
    # Retail / Marketplaces
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

async def send_notification(summary: dict, error: Optional[str] = None):
    """Envía un resumen de ejecución a ntfy.sh, Discord o Telegram."""
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    ntfy_topic = os.environ.get("NTFY_TOPIC")

    if not telegram_token and not discord_webhook and not ntfy_topic:
        logger.info("Notificaciones no configuradas (NTFY_TOPIC, TELEGRAM_BOT_TOKEN o DISCORD_WEBHOOK_URL no definidos).")
        return

    now_ar = time.strftime("%d/%m/%Y %H:%M")
    if error:
        text = (
            f"🚨 *SuperVmarket Scraper — ERROR*\n\n"
            f"📅 *Fecha:* {now_ar} (ARG)\n"
            f"❌ *Detalle:* `{error}`"
        )
    else:
        stores_txt = "\n".join([f"  • *{st}*: {cnt:,} prods" for st, cnt in summary.get("stores", {}).items() if cnt > 0])
        text = (
            f"🛒 *SuperVmarket — Scraping Diario Exitoso*\n\n"
            f"📅 *Fecha:* {now_ar} (ARG)\n"
            f"⏱️ *Duración:* {summary.get('duration_str', 'N/A')}\n\n"
            f"📦 *Productos por Tienda:*\n{stores_txt}\n\n"
            f"✅ *Total en Turso Cloud:* {summary.get('total_prods', 0):,} productos actualizados."
        )

    async with turso.httpx.AsyncClient(timeout=10.0) as client:
        # 1. ntfy.sh (Push instantánea)
        if ntfy_topic:
            try:
                clean_text = text.replace("*", "").replace("`", "")
                resp = await client.post(
                    f"https://ntfy.sh/{ntfy_topic}",
                    content=clean_text.encode("utf-8"),
                    headers={
                        "Title": "SuperVmarket Scraper Diario" if not error else "SuperVmarket Error",
                        "Priority": "default" if not error else "high",
                        "Tags": "shopping_cart,supermarket" if not error else "warning,rotating_light",
                    },
                )
                if resp.status_code == 200:
                    logger.info("Notificación enviada a ntfy.sh (%s) con éxito.", ntfy_topic)
            except Exception as e:
                logger.warning("Error enviando notificación a ntfy.sh: %s", e)

        # 2. Discord Webhook
        if discord_webhook:
            try:
                resp = await client.post(discord_webhook, json={"content": text})
                if resp.status_code in (200, 204):
                    logger.info("Notificación enviada a Discord con éxito.")
            except Exception as e:
                logger.warning("Error enviando notificación a Discord: %s", e)

        # 3. Telegram Bot
        if telegram_token and telegram_chat_id:
            try:
                tg_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                resp = await client.post(tg_url, json={
                    "chat_id": telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
                if resp.status_code == 200:
                    logger.info("Notificación enviada a Telegram con éxito.")
            except Exception as e:
                logger.warning("Error enviando notificación a Telegram: %s", e)

async def run_scraper(
    mode: str = "total",
    stores: Optional[List[str]] = None,
    max_items_per_store: Optional[int] = None,
    batch_size: int = BATCH_SIZE,
):
    if not turso.IS_TURSO_CONFIGURED:
        logger.error("TURSO_DATABASE_URL o TURSO_AUTH_TOKEN faltantes. Abortando.")
        return

    active_stores = stores or DEFAULT_STORES
    is_total_mode = (mode == "total")

    logger.info("=================================================================")
    logger.info("SCRAPER DIARIO SUPERVMARKET (MODO: %s)", "CATÁLOGO COMPLETO" if is_total_mode else "SEMILLAS")
    logger.info("Tiendas a procesar (%d): %s", len(active_stores), ", ".join(active_stores))
    if max_items_per_store:
        logger.info("Límite máximo por tienda: %d ítems", max_items_per_store)
    else:
        logger.info("Límite por tienda: ILIMITADO (catálogo activo completo)")
    logger.info("=================================================================")

    total_prods = 0
    total_precios = 0
    store_summary: Dict[str, int] = {}
    start_time = time.time()

    prod_buffer: list = []
    precio_buffer: list = []

    limits = turso.httpx.Limits(max_connections=50, max_keepalive_connections=20, keepalive_expiry=30.0)
    async with turso.httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        for store in active_stores:
            store_start = time.time()
            store_count = 0
            logger.info(">>> Iniciando scraping de %s <<<", store)

            try:
                if store == "MercadoLibre":
                    from api._lib.mercadolibre import fetch_mercadolibre_live
                    queries = ["alimentos y bebidas", "lacteos y frescos", "limpieza del hogar", "cuidado personal", "bebidas", "smartphones celulares", "smart tv televisores"]
                    for query in queries:
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
                    # Ingesta masiva en lotes de 50 por árbol de categorías y Endeca
                    async for item in harvest_store(
                        store_key=store,
                        categories_or_seeds=DEPARTMENTAL_SEEDS[:20] if not is_total_mode else None,
                        max_items=max_items_per_store,
                        seeds_only=not is_total_mode,
                        include_sitemap=False,
                    ):
                        p_val = _safe_float(item.get("price_raw"), 0.0)
                        if p_val <= 0:
                            continue

                        title = item.get("title_raw") or ""
                        brand = item.get("brand_raw") or ""
                        ext_id = str(item.get("external_id") or "")
                        ean_cand = resolve_product_ean(store, ext_id, str(item.get("ean_raw") or ""))
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
                store_summary[store] = store_count
                logger.info("Tienda %s finalizada: %d productos en %.1fs", store, store_count, time.time() - store_start)

            except Exception as e:
                logger.error("Error durante scraping de %s: %s", store, e, exc_info=True)

    duration = time.time() - start_time
    logger.info("=================================================================")
    logger.info("Scraper finalizado con éxito en %.1f segundos.", duration)
    logger.info("Total ítems procesados: %d productos / %d precios.", total_prods, total_precios)
    logger.info("=================================================================")

    summary_data = {
        "duration_seconds": duration,
        "duration_str": f"{int(duration // 60)}m {int(duration % 60)}s" if duration >= 60 else f"{duration:.1f}s",
        "total_prods": total_prods,
        "total_precios": total_precios,
        "stores": store_summary,
    }
    await send_notification(summary_data)

def main():
    parser = argparse.ArgumentParser(description="SuperVmarket Fast Category & Endeca Scraper")
    parser.add_argument(
        "--mode",
        choices=["total", "seeds"],
        default="total",
        help="Modo de ejecución: 'total' (catálogo activo completo por árbol de categorías) o 'seeds' (muestreo)",
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
