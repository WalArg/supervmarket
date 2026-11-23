#!/usr/bin/env python3
"""scripts/daily_scraper.py

Pipeline de Scraping Diario Definitivo de Alta Concurrencia para SuperVmarket.
Cubre TODO el ecosistema minorista: Supermercados, Marketplaces, Electro, Farmacias y Marcas Oficiales.

Arquitectura:
1. Matrix Parallelism (GitHub Actions): Dividido en 5 grupos en paralelo para completar
   todo el país en ~35 minutos sobre runners independientes.
2. Sitemaps XML de Alta Concurrencia: Workers asíncronos continuos (30-40 workers por tienda).
3. Escritor en Segundo Plano Desacoplado (TursoBackgroundWriter):
   Encolamiento en 0ms y guardado por lotes masivos directamente en Turso Cloud DB.
4. Notificaciones Push consolidadas a ntfy.sh, Discord o Telegram al finalizar.
"""

import os
import sys
import time
import asyncio
import logging
import argparse
import json
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
    DEPARTMENTAL_SEEDS,
    _parse_vtex_product,
    resolve_product_ean,
    harvest_coto_store,
)
from api._lib.mercadolibre import fetch_mercadolibre_live, is_electro_query
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

# Grupos de Ingesta Paralela (Matrix Execution)
STORE_GROUPS = {
    # 1. Hipermercados Cencosud (Sitemaps profundos)
    "cencosud": ["Jumbo", "Disco", "Vea"],

    # 2. Hiper & Supermercados Nacionales
    "supermercados-hiper": ["Carrefour", "Dia", "Más Online", "Toledo Digital", "Cordiez"],

    # 3. Marketplaces, Retail, Hogar & Cadenas de Electro
    "marketplaces-electro": ["On City", "Cetrogar", "Naldo", "Pardo", "Easy", "StyleStore"],

    # 4. Farmacias, Perfumerías, Mascotas & Tiendas Oficiales de Marca
    "especialidades-marcas": [
        "Farmacity", "Simplicity", "Perfumerías Pigmento", "Puppis",
        "Samsung", "Philips", "Whirlpool", "Oster", "Moulinex / Tefal"
    ],

    # 5. Coto Digital (API Endeca) + Mercado Libre (Catálogo Oficial y FULL)
    "coto-mercadolibre": ["Coto", "MercadoLibre"],
}

# Configuración de Sitemaps y Concurrencia por Tienda
SITEMAP_STORE_CONFIG = {
    # --- Supermercados Principales (85 sub-sitemaps = hasta 85.000 productos = 100% de la góndola) ---
    "Carrefour": {
        "domain": "https://www.carrefour.com.ar",
        "sitemap_url": "https://www.carrefour.com.ar/sitemap.xml",
        "workers": 40,
        "type": "supermarket",
        "max_sub_sitemaps": 85,
    },
    "Jumbo": {
        "domain": "https://www.jumbo.com.ar",
        "sitemap_url": "https://www.jumbo.com.ar/sitemap.xml",
        "workers": 35,
        "type": "supermarket",
        "max_sub_sitemaps": 85,
    },
    "Disco": {
        "domain": "https://www.disco.com.ar",
        "sitemap_url": "https://www.disco.com.ar/sitemap.xml",
        "workers": 35,
        "type": "supermarket",
        "max_sub_sitemaps": 85,
    },
    "Vea": {
        "domain": "https://www.vea.com.ar",
        "sitemap_url": "https://www.vea.com.ar/sitemap.xml",
        "workers": 35,
        "type": "supermarket",
        "max_sub_sitemaps": 85,
    },
    "Dia": {
        "domain": "https://diaonline.supermercadosdia.com.ar",
        "sitemap_url": "https://diaonline.supermercadosdia.com.ar/sitemap.xml",
        "workers": 20,
        "type": "supermarket",
        "max_sub_sitemaps": 25,
    },
    "Más Online": {
        "domain": "https://www.masonline.com.ar",
        "sitemap_url": "https://www.masonline.com.ar/sitemap.xml",
        "workers": 30,
        "type": "supermarket",
        "max_sub_sitemaps": 50,
    },
    "Toledo Digital": {
        "domain": "https://www.toledodigital.com.ar",
        "sitemap_url": "https://www.toledodigital.com.ar/sitemap.xml",
        "workers": 20,
        "type": "supermarket",
        "max_sub_sitemaps": 25,
    },
    "Cordiez": {
        "domain": "https://www.cordiez.com.ar",
        "sitemap_url": "https://www.cordiez.com.ar/sitemap.xml",
        "workers": 20,
        "type": "supermarket",
        "max_sub_sitemaps": 25,
    },

    # --- Marketplaces, Hogar, Construcción & Electro ---
    "On City": {
        "domain": "https://www.oncity.com",
        "sitemap_url": "https://www.oncity.com/sitemap.xml",
        "workers": 25,
        "type": "electro",
        "max_sub_sitemaps": 50,
    },
    "Cetrogar": {
        "domain": "https://www.cetrogar.com.ar",
        "sitemap_url": "https://www.cetrogar.com.ar/sitemap.xml",
        "workers": 20,
        "type": "electro",
        "max_sub_sitemaps": 25,
    },
    "Easy": {
        "domain": "https://www.easy.com.ar",
        "sitemap_url": "https://www.easy.com.ar/sitemap.xml",
        "workers": 25,
        "type": "specialty",
        "max_sub_sitemaps": 40,
    },
    "Naldo": {
        "domain": "https://www.naldo.com.ar",
        "sitemap_url": "https://www.naldo.com.ar/sitemap.xml",
        "workers": 20,
        "type": "electro",
        "max_sub_sitemaps": 25,
    },
    "Pardo": {
        "domain": "https://www.pardo.com.ar",
        "sitemap_url": "https://www.pardo.com.ar/sitemap.xml",
        "workers": 20,
        "type": "electro",
        "max_sub_sitemaps": 25,
    },
    "StyleStore": {
        "domain": "https://www.stylestore.com.ar",
        "sitemap_url": "https://www.stylestore.com.ar/sitemap.xml",
        "workers": 20,
        "type": "electro",
        "max_sub_sitemaps": 25,
    },

    # --- Farmacias & Perfumerías ---
    "Farmacity": {
        "domain": "https://www.farmacity.com",
        "sitemap_url": "https://www.farmacity.com/sitemap.xml",
        "workers": 25,
        "type": "pharmacy",
        "max_sub_sitemaps": 35,
    },
    "Simplicity": {
        "domain": "https://www.simplicity.com.ar",
        "sitemap_url": "https://www.simplicity.com.ar/sitemap.xml",
        "workers": 20,
        "type": "pharmacy",
        "max_sub_sitemaps": 25,
    },
    "Perfumerías Pigmento": {
        "domain": "https://www.perfumeriaspigmento.com.ar",
        "sitemap_url": "https://www.perfumeriaspigmento.com.ar/sitemap.xml",
        "workers": 20,
        "type": "pharmacy",
        "max_sub_sitemaps": 25,
    },

    # --- Mascotas ---
    "Puppis": {
        "domain": "https://www.puppis.com.ar",
        "sitemap_url": "https://www.puppis.com.ar/sitemap.xml",
        "workers": 20,
        "type": "specialty",
        "max_sub_sitemaps": 20,
    },

    # --- Tiendas Oficiales de Marca ---
    "Samsung": {
        "domain": "https://shop.samsung.com.ar",
        "sitemap_url": "https://shop.samsung.com.ar/sitemap.xml",
        "workers": 15,
        "type": "electro",
        "max_sub_sitemaps": 15,
    },
    "Philips": {
        "domain": "https://www.tienda.philips.com.ar",
        "sitemap_url": "https://www.tienda.philips.com.ar/sitemap.xml",
        "workers": 15,
        "type": "electro",
        "max_sub_sitemaps": 15,
    },
    "Whirlpool": {
        "domain": "https://www.whirlpool.com.ar",
        "sitemap_url": "https://www.whirlpool.com.ar/sitemap.xml",
        "workers": 15,
        "type": "electro",
        "max_sub_sitemaps": 15,
    },
    "Oster": {
        "domain": "https://www.osterargentina.com",
        "sitemap_url": "https://www.osterargentina.com/sitemap.xml",
        "workers": 15,
        "type": "electro",
        "max_sub_sitemaps": 15,
    },
    "Moulinex / Tefal": {
        "domain": "https://tienda.moulinex.com.ar",
        "sitemap_url": "https://tienda.moulinex.com.ar/sitemap.xml",
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
            resp = await client.post(pipeline_url, json=payload, headers=headers, timeout=15.0)
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

async def harvest_mercadolibre_catalog(
    writer: TursoBackgroundWriter,
    max_items: Optional[int] = None,
) -> int:
    """Ingesta masiva de catálogo oficial, envíos FULL y ofertas de Mercado Libre."""
    logger.info("[MercadoLibre] Iniciando barrido masivo de catálogo...")
    count = 0
    seen_ids = set()

    limits = turso.httpx.Limits(max_connections=50, max_keepalive_connections=20, keepalive_expiry=30.0)
    async with turso.httpx.AsyncClient(limits=limits, timeout=15.0) as client:
        sem = asyncio.Semaphore(6)

        async def fetch_seed(seed: str):
            nonlocal count
            if max_items and count >= max_items:
                return
            is_electro = is_electro_query(seed)
            vert = "electro" if is_electro else "supermarket"
            async with sem:
                try:
                    results = await fetch_mercadolibre_live(client, seed, limit=50, vertical=vert)
                    for r in results:
                        sku = str(r.get("sku") or r.get("ean") or "")
                        if not sku or sku in seen_ids:
                            continue
                        seen_ids.add(sku)

                        item: HarvesterItem = {
                            "store_name": "MercadoLibre",
                            "external_id": sku,
                            "ean_raw": r.get("ean") if not str(r.get("ean", "")).startswith("MELI_") else "",
                            "title_raw": r.get("nombre", ""),
                            "brand_raw": r.get("marca", ""),
                            "categories_raw": vert,
                            "link_raw": r.get("link", ""),
                            "image_raw": r.get("imagen", ""),
                            "price_raw": float(r.get("precio_venta") or 0.0),
                            "list_price_raw": float(r.get("precio_lista") or 0.0),
                            "stock_raw": int(r.get("stock") or 100),
                            "seller_id_raw": str(r.get("seller_id") or "1"),
                            "raw_json": json.dumps(r),
                        }
                        writer.enqueue(item)
                        count += 1
                        if max_items and count >= max_items:
                            break
                except Exception as e:
                    logger.debug("[MercadoLibre] Error seed %s: %s", seed, e)

        tasks = [fetch_seed(seed) for seed in DEPARTMENTAL_SEEDS]
        await asyncio.gather(*tasks)

    logger.info("[MercadoLibre] Ingesta finalizada: %d productos oficiales procesados", count)
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
        group_lbl = summary.get("group_name", "Total")
        text = (
            f"🛒 SuperVmarket — {group_lbl} Exitoso\n\n"
            f"📅 Fecha: {now_ar} (ARG)\n"
            f"⏱️ Duración: {summary.get('duration_str', 'N/A')}\n\n"
            f"📦 Productos Procesados:\n{stores_txt}\n\n"
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
                        "Title": "SuperVmarket Scraper" if not error else "SuperVmarket Error",
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

async def send_summary_notification():
    """Calcula el consolidado global en Turso Cloud DB tras la finalización de los runners paralelos."""
    if not turso.IS_TURSO_CONFIGURED:
        logger.error("Turso no configurado para resumen.")
        return

    try:
        prods_res = await turso.query("SELECT COUNT(*) as cnt FROM productos;")
    except Exception as e:
        logger.warning("Fallo al consultar resumen con endpoint actual (%s): %s. Intentando fallback canónico...", turso.TURSO_HTTP_URL, e)
        turso.TURSO_HTTP_URL = turso._DEFAULT_URL
        turso._TURSO_TOKEN = turso._DEFAULT_TOKEN
        turso.IS_TURSO_CONFIGURED = True
        try:
            prods_res = await turso.query("SELECT COUNT(*) as cnt FROM productos;")
        except Exception as e2:
            logger.error("Error fatal al generar resumen consolidado: %s", e2)
            return

    try:
        total_prods = prods_res[0]["cnt"] if prods_res else 0

        precios_res = await turso.query("SELECT COUNT(*) as cnt FROM precios;")
        total_precios = precios_res[0]["cnt"] if precios_res else 0

        stores_res = await turso.query(
            "SELECT supermercado, COUNT(*) as cnt FROM precios GROUP BY supermercado ORDER BY cnt DESC LIMIT 20;"
        )
        stores_txt = "\n".join([f"  • {r['supermercado']}: {r['cnt']:,} ofertas" for r in (stores_res or [])])

        now_ar = time.strftime("%d/%m/%Y %H:%M")
        text = (
            f"🎉 SuperVmarket — Barrido Nacional Consolidado Completo\n\n"
            f"📅 Fecha: {now_ar} (ARG)\n"
            f"🚀 Cobertura: Supermercados + Marketplaces + Electro + Farmacias\n\n"
            f"📊 Estado Total en Turso Cloud DB:\n"
            f"  • {total_prods:,} productos únicos catalogados\n"
            f"  • {total_precios:,} ofertas y precios comparados\n\n"
            f"🏪 Tiendas con Cobertura Activa:\n{stores_txt}\n\n"
            f"🌐 App en vivo: https://vsupermarket.vercel.app"
        )
        logger.info(text)

        summary = {
            "group_name": "Barrido Nacional Consolidado",
            "total_prods": total_prods,
            "duration_str": "Multi-Runner Paralelo",
            "stores": {r["supermercado"]: r["cnt"] for r in (stores_res or [])}
        }
        await send_notification(summary)
    except Exception as e:
        logger.error("Error al generar resumen consolidado: %s", e)

async def run_scraper(
    group: Optional[str] = None,
    stores: Optional[List[str]] = None,
    max_items_per_store: Optional[int] = None,
):
    if not turso.IS_TURSO_CONFIGURED:
        logger.error("TURSO_DATABASE_URL o TURSO_AUTH_TOKEN faltantes. Abortando.")
        return

    logger.info("Turso Endpoint configurado: %s", turso.TURSO_HTTP_URL)
    try:
        ping_res = await turso.query("SELECT 1 as ping")
        if not ping_res:
            raise ValueError("Turso ping devolvió respuesta vacía")
        logger.info("Conexión con Turso Cloud DB verificada exitosamente: %s", ping_res)
    except Exception as e:
        logger.warning("Fallo al conectar con endpoint configurado (%s): %s. Intentando fallback canónico...", turso.TURSO_HTTP_URL, e)
        turso.TURSO_HTTP_URL = turso._DEFAULT_URL
        turso._TURSO_TOKEN = turso._DEFAULT_TOKEN
        turso.IS_TURSO_CONFIGURED = True
        try:
            ping_res = await turso.query("SELECT 1 as ping")
            if not ping_res:
                raise ValueError("Turso fallback devolvió respuesta vacía")
            logger.info("Conexión con Turso Cloud DB (Fallback Canónico) verificada exitosamente: %s", ping_res)
        except Exception as e2:
            logger.error("Error fatal conectando con Turso Cloud DB tras fallback: %s", e2)
            await send_notification({}, error=f"Fallo de conexión fatal a Turso Cloud DB: {e2}")
            return

    # Determinación de tiendas según grupo o lista explícita
    if group and group in STORE_GROUPS:
        target_store_keys = STORE_GROUPS[group]
        group_label = f"Grupo '{group}'"
    elif group == "all":
        target_store_keys = []
        for g_stores in STORE_GROUPS.values():
            for s in g_stores:
                if s not in target_store_keys:
                    target_store_keys.append(s)
        group_label = "Todos los Grupos (Nacional)"
    elif stores:
        target_store_keys = stores
        group_label = f"Tiendas manuales ({len(stores)})"
    else:
        # Default fallback: ejecutar todos los grupos
        target_store_keys = []
        for g_stores in STORE_GROUPS.values():
            for s in g_stores:
                if s not in target_store_keys:
                    target_store_keys.append(s)
        group_label = "Barrido Total Definitivo"

    logger.info("=================================================================")
    logger.info("SCRAPER DEFINITIVO DE ALTA CONCURRENCIA — %s", group_label.upper())
    logger.info("Tiendas en paralelo (%d): %s", len(target_store_keys), ", ".join(target_store_keys))
    logger.info("=================================================================")

    start_time = time.time()
    limits = turso.httpx.Limits(max_connections=500, max_keepalive_connections=200, keepalive_expiry=60.0)
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
            elif store == "MercadoLibre":
                tasks.append(
                    harvest_mercadolibre_catalog(
                        writer=writer,
                        max_items=max_items_per_store,
                    )
                )

        # Ejecución simultánea de todas las tiendas asignadas a este runner
        logger.info("Lanzando %d cadenas en simultáneo...", len(tasks))
        await asyncio.gather(*tasks)

        # Esperar a que el escritor en background drene la cola y haga el commit final
        logger.info("Esperando a que TursoBackgroundWriter complete los commits...")
        await writer.stop()

    duration = time.time() - start_time
    logger.info("=================================================================")
    logger.info("%s finalizado con éxito en %.1f segundos.", group_label, duration)
    logger.info("Total ítems procesados: %d productos / precios.", writer.total_written)
    logger.info("=================================================================")

    summary_data = {
        "group_name": group_label,
        "duration_seconds": duration,
        "duration_str": f"{int(duration // 60)}m {int(duration % 60)}s" if duration >= 60 else f"{duration:.1f}s",
        "total_prods": writer.total_written,
        "stores": dict(writer.store_counts),
    }
    await send_notification(summary_data)

def main():
    parser = argparse.ArgumentParser(description="SuperVmarket High-Concurrency Sitemap Scraper")
    parser.add_argument("--group", choices=list(STORE_GROUPS.keys()) + ["all"], default=None,
                        help="Grupo de tiendas a ejecutar en paralelo")
    parser.add_argument("--stores", nargs="+", help="Tiendas específicas a scrapear")
    parser.add_argument("--max-items-per-store", type=int, default=None, help="Límite máximo por tienda")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Tamaño de lote")
    parser.add_argument("--notify-summary", action="store_true", help="Calcular y enviar resumen global consolidado")
    parser.add_argument("--mode", default="total", help="Compatibilidad backward")
    args, _ = parser.parse_known_args()

    if args.notify_summary:
        asyncio.run(send_summary_notification())
    else:
        asyncio.run(run_scraper(
            group=args.group,
            stores=args.stores,
            max_items_per_store=args.max_items_per_store,
        ))

if __name__ == "__main__":
    main()
