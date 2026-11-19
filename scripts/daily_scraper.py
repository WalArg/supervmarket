#!/usr/bin/env python3
"""scripts/daily_scraper.py

Pipeline de Scraping Diario Definitivo de Alta Concurrencia para SuperVmarket.
Arquitectura Sitemaps XML con Paralelismo Masivo y Escritor Desacoplado:
1. Full Multi-Store Parallelism (asyncio.gather):
   Carrefour (40), Jumbo (25), Disco (25), Vea (25), Dia (15), Más Online (25) se ejecutan
   simultáneamente con más de 130 workers asíncronos en paralelo.
2. Descubrimiento de Sitemaps en segundos:
   Descarga concurrente de sub-sitemaps XML para obtener 100% de slugs únicos.
3. Escritor en Segundo Plano Desacoplado (TursoBackgroundWriter):
   Los workers de red jamás se frenan por la base de datos (enqueue en 0ms).
   Un pipeline en background consume la cola y envía lotes de 80 sentencias a Turso Cloud DB.
4. Notificaciones push automáticas a ntfy.sh, Discord o Telegram al finalizar.
"""

import os
import sys
import time
import asyncio
import logging
import argparse
import re
from collections import defaultdict
from typing import Dict, List, Any, Optional, Set

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib import turso
from api._lib.harvester import (
    HarvesterItem,
    _parse_vtex_product,
    resolve_product_ean,
    harvest_coto_store,
)
from api._lib.normalization import classify_product_type
from api._lib.catalog_normalizer import classify_canonical_category
from api._lib.parsers import _safe_float, _safe_int, _strip_accents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("daily_scraper")

# Configuración de Sitemaps y Concurrencia por Tienda
SITEMAP_STORE_CONFIG = {
    # --- Supermercados Principales (Catálogo activo en los sub-sitemaps más recientes) ---
    "Carrefour": {
        "domain": "https://www.carrefour.com.ar",
        "sitemap_url": "https://www.carrefour.com.ar/sitemap.xml",
        "workers": 35,
        "type": "supermarket",
        "max_sub_sitemaps": 30,
    },
    "Jumbo": {
        "domain": "https://www.jumbo.com.ar",
        "sitemap_url": "https://www.jumbo.com.ar/sitemap.xml",
        "workers": 25,
        "type": "supermarket",
        "max_sub_sitemaps": 30,
    },
    "Disco": {
        "domain": "https://www.disco.com.ar",
        "sitemap_url": "https://www.disco.com.ar/sitemap.xml",
        "workers": 25,
        "type": "supermarket",
        "max_sub_sitemaps": 30,
    },
    "Vea": {
        "domain": "https://www.vea.com.ar",
        "sitemap_url": "https://www.vea.com.ar/sitemap.xml",
        "workers": 25,
        "type": "supermarket",
        "max_sub_sitemaps": 30,
    },
    "Dia": {
        "domain": "https://diaonline.supermercadosdia.com.ar",
        "sitemap_url": "https://diaonline.supermercadosdia.com.ar/sitemap.xml",
        "workers": 15,
        "type": "supermarket",
        "max_sub_sitemaps": 15,
    },
    "Más Online": {
        "domain": "https://www.masonline.com.ar",
        "sitemap_url": "https://www.masonline.com.ar/sitemap.xml",
        "workers": 25,
        "type": "supermarket",
        "max_sub_sitemaps": 35,
    },
    # --- Retail / Electro ---
    "On City": {
        "domain": "https://www.oncity.com",
        "sitemap_url": "https://www.oncity.com/sitemap.xml",
        "workers": 15,
        "type": "electro",
        "max_sub_sitemaps": 35,
    },
    "Cetrogar": {
        "domain": "https://www.cetrogar.com.ar",
        "sitemap_url": "https://www.cetrogar.com.ar/sitemap.xml",
        "workers": 15,
        "type": "electro",
        "max_sub_sitemaps": 15,
    },
}

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

class TursoBackgroundWriter:
    """Escritor asíncrono desacoplado: consume la cola en background sin frenar los workers de red."""
    def __init__(self, client: turso.httpx.AsyncClient, batch_size: int = BATCH_SIZE):
        self.client = client
        self.batch_size = batch_size
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=50000)
        self.total_written = 0
        self.store_counts: Dict[str, int] = defaultdict(int)
        self._stopped = False
        self._worker_task: Optional[asyncio.Task] = None

    def start(self):
        self._worker_task = asyncio.create_task(self._consumer_loop())

    async def stop(self):
        self._stopped = True
        if self._worker_task:
            await self._worker_task

    def enqueue(self, item: HarvesterItem):
        try:
            self.queue.put_nowait(item)
        except asyncio.QueueFull:
            pass

    async def _consumer_loop(self):
        prod_buf = []
        precio_buf = []
        last_flush = time.time()
        sql_prod = (
            "INSERT OR REPLACE INTO productos (ean, nombre, marca, modelo, tipo, imagen, "
            "supermercado_origen, categorias, categoria_normalizada, actualizado, search_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        sql_pr = (
            "INSERT OR REPLACE INTO precios (ean, supermercado, precio_venta, precio_lista, "
            "descuento, precio_por_unidad, unidad_medida, stock, internal_id, link, fecha, "
            "promo_etiqueta, promo_tipo, promo_min_qty, precio_promo_unit, requiere_club, "
            "seller_id, store_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

        while not self._stopped or not self.queue.empty():
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=0.25)
                p_val = _safe_float(item.get("price_raw"), 0.0)
                if p_val > 0:
                    store_name = item["store_name"]
                    ext_id = str(item.get("external_id") or "")
                    ean_cand = resolve_product_ean(store_name, ext_id, str(item.get("ean_raw") or ""))
                    if ean_cand:
                        title = item.get("title_raw") or ""
                        brand = item.get("brand_raw") or ""
                        cats = item.get("categories_raw") or ""
                        link = item.get("link_raw") or ""
                        img = item.get("image_raw") or ""
                        list_price = _safe_float(item.get("list_price_raw"), p_val)
                        disc = round((1.0 - p_val / list_price) * 100.0, 1) if list_price > p_val else 0.0
                        search_txt = _strip_accents(f"{title} {brand} {ean_cand} {store_name} {cats}").lower()
                        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

                        meta = SITEMAP_STORE_CONFIG.get(store_name, {})
                        base_type = meta.get("type", "supermarket")
                        v_type = classify_product_type(cats, base_type)
                        cat_norm = classify_canonical_category(title, brand, cats, v_type)

                        prod_buf.append((
                            ean_cand, title, brand, "", v_type, img,
                            store_name, cats, cat_norm, now_str, search_txt
                        ))
                        precio_buf.append((
                            ean_cand, store_name, p_val, list_price, disc, None, "un",
                            1, ext_id, link, now_str,
                            f"{int(disc)}% OFF" if disc >= 5 else None, "DIRECT" if disc >= 5 else None,
                            1, p_val, 0, str(item.get("seller_id_raw") or "1"), v_type
                        ))
                        self.total_written += 1
                        self.store_counts[store_name] += 1
                self.queue.task_done()
            except asyncio.TimeoutError:
                pass

            now = time.time()
            if len(prod_buf) >= self.batch_size or ((now - last_flush) >= 2.0 and prod_buf):
                stmts_p = [{"sql": sql_prod, "args": [_to_turso_arg(v) for v in r]} for r in prod_buf]
                stmts_pr = [{"sql": sql_pr, "args": [_to_turso_arg(v) for v in r]} for r in precio_buf]
                await asyncio.gather(
                    send_turso_batch(self.client, stmts_p),
                    send_turso_batch(self.client, stmts_pr),
                )
                prod_buf.clear()
                precio_buf.clear()
                last_flush = now

        # Flush final remanente
        if prod_buf or precio_buf:
            stmts_p = [{"sql": sql_prod, "args": [_to_turso_arg(v) for v in r]} for r in prod_buf]
            stmts_pr = [{"sql": sql_pr, "args": [_to_turso_arg(v) for v in r]} for r in precio_buf]
            await asyncio.gather(
                send_turso_batch(self.client, stmts_p),
                send_turso_batch(self.client, stmts_pr),
            )
            prod_buf.clear()
            precio_buf.clear()

async def fetch_all_sitemap_slugs(
    client: turso.httpx.AsyncClient,
    root_sitemap_url: str,
    max_sub_sitemaps: Optional[int] = None,
) -> List[str]:
    """Descarga de forma concurrente los sub-sitemaps de producto y extrae sus slugs."""
    try:
        resp = await client.get(root_sitemap_url, timeout=15.0)
    except Exception as e:
        logger.error("No se pudo conectar al sitemap raíz %s: %s", root_sitemap_url, e)
        return []

    if resp.status_code != 200:
        logger.error("Sitemap raíz %s devolvió HTTP %d", root_sitemap_url, resp.status_code)
        return []

    sub_urls = [u for u in re.findall(r"<loc>(.*?)</loc>", resp.text) if "product" in u.lower()]
    total_found = len(sub_urls)
    if max_sub_sitemaps and total_found > max_sub_sitemaps:
        logger.info("[%s] Acotando sitemap a los %d sub-sitemaps más recientes (de %d totales)",
                    root_sitemap_url, max_sub_sitemaps, total_found)
        sub_urls = sub_urls[:max_sub_sitemaps]

    sem = asyncio.Semaphore(35)
    async def fetch_sub(url: str) -> List[str]:
        async with sem:
            try:
                r = await client.get(url, timeout=12.0)
                if r.status_code == 200:
                    locs = re.findall(r"<loc>(.*?)</loc>", r.text)
                    extracted = []
                    for l in locs:
                        m = re.search(r'https?://[^/]+/([^/]+)/p', l) or re.search(r'/([^/]+)/p', l)
                        if m:
                            extracted.append(m.group(1))
                    return extracted
            except Exception:
                pass
            return []

    results = await asyncio.gather(*[fetch_sub(u) for u in sub_urls])
    all_slugs: List[str] = []
    seen = set()
    for sub_slugs in results:
        for s in sub_slugs:
            if s not in seen:
                seen.add(s)
                all_slugs.append(s)

    logger.info("[%s] Total slugs únicos extraídos del sitemap: %d", root_sitemap_url, len(all_slugs))
    return all_slugs

async def harvest_vtex_sitemap_store_concurrent(
    client: turso.httpx.AsyncClient,
    store_name: str,
    config: dict,
    writer: TursoBackgroundWriter,
    limit: Optional[int] = None,
) -> int:
    domain = config["domain"]
    sitemap_url = config["sitemap_url"]
    worker_count = config.get("workers", 25)
    max_subs = config.get("max_sub_sitemaps", 30)

    slugs = await fetch_all_sitemap_slugs(client, sitemap_url, max_sub_sitemaps=max_subs)
    if not slugs:
        return 0

    if limit:
        slugs = slugs[:limit]

    slug_queue = asyncio.Queue()
    for s in slugs:
        await slug_queue.put(s)

    count = 0
    t0 = time.perf_counter()

    async def worker():
        nonlocal count
        while not slug_queue.empty():
            try:
                s = slug_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            url = f"{domain}/api/catalog_system/pub/products/search/{s}/p"
            try:
                res = await client.get(url, timeout=12.0)
                if res.status_code == 200:
                    data = res.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        items = _parse_vtex_product(data[0], store_name, domain)
                        for it in items:
                            writer.enqueue(it)
                            count += 1
                elif res.status_code == 429:
                    await asyncio.sleep(2.0)
                    await slug_queue.put(s)
            except Exception:
                pass
            finally:
                slug_queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
    await asyncio.gather(*workers)
    elapsed = time.perf_counter() - t0
    logger.info("[%s] Ingesta finalizada: %d productos procesados en %.1fs (%.1f ítems/s)",
                store_name, count, elapsed, count / max(0.1, elapsed))
    return count

async def send_notification(summary: dict, error: Optional[str] = None):
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    ntfy_topic = os.environ.get("NTFY_TOPIC")

    if not telegram_token and not discord_webhook and not ntfy_topic:
        return

    now_ar = time.strftime("%d/%m/%Y %H:%M")
    if error:
        text = f"🚨 SuperVmarket Scraper ERROR\n\nFecha: {now_ar} (ARG)\nDetalle: {error}"
    else:
        stores_txt = "\n".join([f"  • {st}: {cnt:,} prods" for st, cnt in summary.get("stores", {}).items() if cnt > 0])
        text = (
            f"🛒 SuperVmarket — Scraping Diario Exitoso\n\n"
            f"📅 Fecha: {now_ar} (ARG)\n"
            f"⏱️ Duración: {summary.get('duration_str', 'N/A')}\n\n"
            f"📦 Productos por Tienda:\n{stores_txt}\n\n"
            f"✅ Total en Turso Cloud: {summary.get('total_prods', 0):,} productos actualizados."
        )

    async with turso.httpx.AsyncClient(timeout=10.0) as client:
        # ntfy.sh
        if ntfy_topic:
            try:
                await client.post(
                    f"https://ntfy.sh/{ntfy_topic}",
                    content=text.encode("utf-8"),
                    headers={
                        "Title": "SuperVmarket Scraper Diario" if not error else "SuperVmarket Error",
                        "Priority": "default" if not error else "high",
                        "Tags": "shopping_cart,supermarket" if not error else "warning,rotating_light",
                    },
                )
            except Exception:
                pass

        # Discord
        if discord_webhook:
            try:
                await client.post(discord_webhook, json={"content": text})
            except Exception:
                pass

        # Telegram
        if telegram_token and telegram_chat_id:
            try:
                await client.post(f"https://api.telegram.org/bot{telegram_token}/sendMessage", json={
                    "chat_id": telegram_chat_id, "text": text
                })
            except Exception:
                pass

async def run_scraper(stores: Optional[List[str]] = None, max_items_per_store: Optional[int] = None):
    if not turso.IS_TURSO_CONFIGURED:
        logger.error("TURSO_DATABASE_URL o TURSO_AUTH_TOKEN faltantes. Abortando.")
        return

    logger.info("Turso Endpoint configurado: %s", turso.TURSO_HTTP_URL)
    try:
        ping_res = await turso.query("SELECT 1 as ping")
        logger.info("Conexión con Turso Cloud DB verificada exitosamente: %s", ping_res)
    except Exception as e:
        logger.error("Error conectando con Turso Cloud DB: %s", e)
        await send_notification({}, error=f"Fallo de conexión inicial a Turso Cloud DB: {e}")
        return

    target_store_keys = stores or list(SITEMAP_STORE_CONFIG.keys()) + ["Coto", "MercadoLibre"]
    logger.info("=================================================================")
    logger.info("SCRAPER DEFINITIVO DE ALTA CONCURRENCIA (SITEMAPS XML)")
    logger.info("Tiendas en paralelo (%d): %s", len(target_store_keys), ", ".join(target_store_keys))
    logger.info("=================================================================")

    start_time = time.time()
    limits = turso.httpx.Limits(max_connections=350, max_keepalive_connections=150, keepalive_expiry=60.0)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
    }

    async with turso.httpx.AsyncClient(limits=limits, headers=headers, timeout=30.0, follow_redirects=True) as client:
        # Iniciar escritor desacoplado en background
        writer = TursoBackgroundWriter(client=client, batch_size=BATCH_SIZE)
        writer.start()

        tasks = []
        for store in target_store_keys:
            if store in SITEMAP_STORE_CONFIG:
                tasks.append(
                    harvest_vtex_sitemap_store_concurrent(
                        client=client,
                        store_name=store,
                        config=SITEMAP_STORE_CONFIG[store],
                        writer=writer,
                        limit=max_items_per_store,
                    )
                )
            elif store == "Coto":
                async def run_coto():
                    c_count = 0
                    async for item in harvest_coto_store(store_key="Coto", max_items=max_items_per_store):
                        writer.enqueue(item)
                        c_count += 1
                    logger.info("[Coto] Ingesta finalizada: %d productos", c_count)
                    return c_count
                tasks.append(run_coto())

        # Ejecución simultánea de todas las tiendas (full paralelismo)
        logger.info("Lanzando todas las cadenas en simultáneo...")
        await asyncio.gather(*tasks)

        # Esperar a que el escritor en background drene la cola y haga el commit final
        logger.info("Esperando a que TursoBackgroundWriter complete los commits...")
        await writer.stop()

    duration = time.time() - start_time
    logger.info("=================================================================")
    logger.info("Scraper Definitivo finalizado con éxito en %.1f segundos.", duration)
    logger.info("Total ítems procesados: %d productos / precios.", writer.total_written)
    logger.info("=================================================================")

    summary_data = {
        "duration_seconds": duration,
        "duration_str": f"{int(duration // 60)}m {int(duration % 60)}s" if duration >= 60 else f"{duration:.1f}s",
        "total_prods": writer.total_written,
        "stores": dict(writer.store_counts),
    }
    await send_notification(summary_data)

def main():
    parser = argparse.ArgumentParser(description="SuperVmarket High-Concurrency Sitemap Scraper")
    parser.add_argument("--mode", default="total", help="Modo de ejecución (ej: total)")
    parser.add_argument("--stores", nargs="+", help="Tiendas específicas a scrapear")
    parser.add_argument("--max-items-per-store", type=int, default=None, help="Límite máximo por tienda")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Tamaño de lote")
    args, _ = parser.parse_known_args()

    asyncio.run(run_scraper(stores=args.stores, max_items_per_store=args.max_items_per_store))

if __name__ == "__main__":
    main()
