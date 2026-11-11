#!/usr/bin/env python3
"""scripts/harvest_fast_sitemaps.py

High-Speed Sitemap & Direct Slug Harvester for VTEX and CDN-backed stores.
Replaces slow category-tree traversal with direct CDN sitemap extraction:
1. Downloads CDN product sub-sitemaps in parallel (<2s for 100k URLs).
2. Delta-deduplicates slugs against existing records in raw_catalog.
3. Fetches missing products concurrently via /api/catalog_system/pub/products/search/{slug}/p
   at 30-60 items/s per store (zero category recursion, zero pagination caps).
4. Writes atomically via DatabaseBatchWriter into raw_catalog, productos, and precios.
"""

import argparse
import asyncio
from collections import defaultdict
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

import httpx

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.harvester import HarvesterItem, _parse_vtex_product, resolve_product_ean
from api._lib.normalization import extract_canonical_model
from api._lib.stores import get_store_meta
from scripts.harvest_all_stores import DatabaseBatchWriter, CheckpointManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("supervmarket.fast_sitemaps")

# Store configuration for fast sitemap harvesting
SITEMAP_STORE_CONFIG = {
    "Carrefour": {
        "domain": "https://www.carrefour.com.ar",
        "sitemap_url": "https://www.carrefour.com.ar/sitemap.xml",
        "concurrency": 25,
    },
    "Jumbo": {
        "domain": "https://www.jumbo.com.ar",
        "sitemap_url": "https://www.jumbo.com.ar/sitemap.xml",
        "concurrency": 20,
    },
    "Disco": {
        "domain": "https://www.disco.com.ar",
        "sitemap_url": "https://www.disco.com.ar/sitemap.xml",
        "concurrency": 20,
    },
    "Vea": {
        "domain": "https://www.vea.com.ar",
        "sitemap_url": "https://www.vea.com.ar/sitemap.xml",
        "concurrency": 20,
    },
}


def get_existing_slugs_from_db(db_path: str, store_name: str) -> Set[str]:
    """Retrieves all product slugs already ingested in raw_catalog for a store."""
    if not os.path.exists(db_path):
        return set()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT link_raw FROM raw_catalog WHERE store_name = ?", (store_name,))
    slugs = set()
    for (link,) in cur.fetchall():
        if link:
            m = re.search(r'/([^/]+)/p', link)
            if m:
                slugs.add(m.group(1))
    conn.close()
    return slugs


async def fetch_all_sitemap_slugs(client: httpx.AsyncClient, root_sitemap_url: str) -> List[str]:
    """Downloads all sub-sitemaps concurrently and extracts unique product slugs."""
    logger.info("Fetching root sitemap: %s", root_sitemap_url)
    resp = await client.get(root_sitemap_url)
    if resp.status_code != 200:
        logger.error("Failed to fetch root sitemap %s: status %d", root_sitemap_url, resp.status_code)
        return []

    sub_urls = [u for u in re.findall(r"<loc>(.*?)</loc>", resp.text) if "product" in u.lower()]
    logger.info("Discovered %d product sub-sitemaps. Downloading concurrently...", len(sub_urls))

    sem = asyncio.Semaphore(25)
    async def fetch_sub(url: str) -> List[str]:
        async with sem:
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    return re.findall(r'/([^/]+)/p', r.text)
            except Exception as e:
                logger.debug("Error fetching sub-sitemap %s: %s", url, e)
            return []

    t0 = time.perf_counter()
    results = await asyncio.gather(*[fetch_sub(u) for u in sub_urls])
    t1 = time.perf_counter()

    all_slugs: List[str] = []
    seen = set()
    for sub_slugs in results:
        for s in sub_slugs:
            if s not in seen:
                seen.add(s)
                all_slugs.append(s)

    logger.info("Extracted %d unique product slugs in %.2fs (%.0f slugs/s)", len(all_slugs), t1 - t0, len(all_slugs) / max(0.1, t1 - t0))
    return all_slugs


async def harvest_sitemap_store(
    store_name: str,
    db_path: str,
    writer_queue: asyncio.Queue,
    limit: Optional[int] = None,
    concurrency: int = 20,
    stop_event: Optional[asyncio.Event] = None,
) -> int:
    """Harvests delta slugs for a store and feeds HarvesterItem objects into writer_queue."""
    config = SITEMAP_STORE_CONFIG.get(store_name)
    if not config:
        logger.error("Store '%s' not recognized in SITEMAP_STORE_CONFIG", store_name)
        return 0

    domain = config["domain"]
    sitemap_url = config["sitemap_url"]
    active_concurrency = concurrency or config.get("concurrency", 20)

    # 1. Deduplication against database
    existing_slugs = get_existing_slugs_from_db(db_path, store_name)
    logger.info("[%s] Existing slugs in raw_catalog: %d", store_name, len(existing_slugs))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }

    async with httpx.AsyncClient(timeout=12.0, headers=headers, follow_redirects=True) as client:
        # 2. Extract sitemap slugs
        all_slugs = await fetch_all_sitemap_slugs(client, sitemap_url)
        if not all_slugs:
            logger.warning("[%s] No slugs found in sitemap.", store_name)
            return 0

        # Filter delta
        delta_slugs = [s for s in all_slugs if s not in existing_slugs]
        logger.info("[%s] Total sitemap slugs: %d | Already in DB: %d | New delta to fetch: %d",
                    store_name, len(all_slugs), len(all_slugs) - len(delta_slugs), len(delta_slugs))

        if limit:
            delta_slugs = delta_slugs[:limit]
            logger.info("[%s] Applying user limit: fetching first %d new slugs", store_name, len(delta_slugs))

        if not delta_slugs:
            logger.info("[%s] All sitemap items already present in database! Nothing to fetch.", store_name)
            return 0

        # 3. Concurrent Slug Resolution
        sem = asyncio.Semaphore(active_concurrency)
        total_items_yielded = 0
        t_start = time.perf_counter()
        last_log = t_start
        slugs_processed = 0

        async def resolve_one_slug(slug: str):
            nonlocal total_items_yielded, slugs_processed, last_log
            if stop_event and stop_event.is_set():
                return

            url = f"{domain}/api/catalog_system/pub/products/search/{slug}/p"
            async with sem:
                try:
                    res = await client.get(url)
                    if res.status_code == 200:
                        data = res.json()
                        if data and isinstance(data, list):
                            items = _parse_vtex_product(data[0], store_name, domain)
                            for it in items:
                                await writer_queue.put(it)
                                total_items_yielded += 1
                except Exception as e:
                    logger.debug("[%s] Error resolving slug '%s': %s", store_name, slug, e)
                finally:
                    slugs_processed += 1
                    now = time.perf_counter()
                    if (now - last_log) >= 5.0:
                        last_log = now
                        elapsed = now - t_start
                        rate = total_items_yielded / max(0.1, elapsed)
                        pct = (slugs_processed / len(delta_slugs)) * 100.0
                        eta = (len(delta_slugs) - slugs_processed) / max(0.1, slugs_processed / elapsed)
                        logger.info(
                            "[%s] Progress: %d/%d slugs (%.1f%%) | Items Ingested: %d | Rate: %.1f items/s | ETA: %.0fs",
                            store_name, slugs_processed, len(delta_slugs), pct, total_items_yielded, rate, eta
                        )

        # Launch slug resolution tasks in chunks of 500 to maintain low memory pressure
        chunk_size = 500
        for i in range(0, len(delta_slugs), chunk_size):
            if stop_event and stop_event.is_set():
                break
            chunk = delta_slugs[i : i + chunk_size]
            await asyncio.gather(*[resolve_one_slug(s) for s in chunk])

        total_elapsed = time.perf_counter() - t_start
        logger.info(
            "[%s] COMPLETED: %d items ingested from %d slugs in %.1fs (%.1f items/s)",
            store_name, total_items_yielded, slugs_processed, total_elapsed, total_items_yielded / max(0.1, total_elapsed)
        )
        return total_items_yielded


async def main():
    import httpx
    globals()["httpx"] = httpx

    parser = argparse.ArgumentParser(description="High-Speed Sitemap Harvester for Supervmarket")
    parser.add_argument("--stores", default="Carrefour,Jumbo,Disco,Vea", help="Comma-separated store names")
    parser.add_argument("--db-path", default="supervmarket.db", help="Path to SQLite database")
    parser.add_argument("--batch-size", type=int, default=250, help="Transaction batch commit size")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent HTTP requests per store")
    parser.add_argument("--limit-per-store", type=int, default=None, help="Max delta slugs to fetch per store")
    parser.add_argument("--checkpoint-file", default=".harvest_fast_sitemaps.json", help="Checkpoint file path")
    args = parser.parse_args()

    target_stores = [s.strip() for s in args.stores.split(",") if s.strip()]
    logger.info("Initializing Fast Sitemap Sweep for stores: %s", target_stores)

    # Initialize Checkpoint & Writer
    checkpoint = CheckpointManager(args.checkpoint_file)
    writer = DatabaseBatchWriter(db_path=args.db_path, batch_size=args.batch_size)
    writer_task = asyncio.create_task(writer.run())

    stop_event = asyncio.Event()

    try:
        for store in target_stores:
            if checkpoint.is_completed(store):
                logger.info("Store '%s' already marked completed in checkpoint. Skipping.", store)
                continue

            count = await harvest_sitemap_store(
                store_name=store,
                db_path=args.db_path,
                writer_queue=writer.queue,
                limit=args.limit_per_store,
                concurrency=args.concurrency,
                stop_event=stop_event,
            )
            checkpoint.mark_completed(store, count)

    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt received! Initiating shutdown...")
        stop_event.set()
    finally:
        # Flush writer queue cleanly
        logger.info("Waiting for database writer to drain remaining queue...")
        while not writer.queue.empty():
            await asyncio.sleep(0.2)
        writer_task.cancel()
        try:
            await writer_task
        except asyncio.CancelledError:
            pass
        logger.info("Database writer flushed cleanly. Total items written: %d", writer.total_written)


if __name__ == "__main__":
    import httpx
    asyncio.run(main())
