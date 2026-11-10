#!/usr/bin/env python3
"""scripts/harvest_all_stores.py

CLI Coordinator para Ingesta Masiva Multitienda con Preservación de Base Cruda.
Características:
1. Concurrencia de red asíncrona desacoplada de la base de datos vía asyncio.Queue(maxsize=5000).
2. Tarea escritora SQLite dedicada con PRAGMA journal_mode = WAL, synchronous = NORMAL, busy_timeout = 30000.
3. Dual-write atómico por lotes (250 filas por transacción) en raw_catalog, productos y precios.
4. Preservación estricta de categoria_normalizada (ON CONFLICT DO UPDATE sin resetear).
5. Claves sintéticas determinísticas {STORE_SLUG}-{external_id} para productos sin EAN-13 GS1 (Zero-Drop Invariant).
6. Checkpointing atómico en .harvest_checkpoint.json con soporte de reanudación (--resume).
7. Reportería de progreso con biblioteca estándar de Python (cero dependencia de rich/tqdm).
8. Captura de señales SIGINT / SIGTERM para vaciado limpio del buffer antes de finalizar.
"""

import argparse
import asyncio
from collections import defaultdict
import json
import logging
import os
import signal
import sqlite3
import sys
import time
from typing import Dict, List, Optional, Set

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.harvester import (
    DEPARTMENTAL_SEEDS,
    HarvesterItem,
    harvest_store,
    resolve_product_ean,
)
from api._lib.normalization import extract_canonical_model
from api._lib.stores import STORE_REGISTRY, StoreMeta, get_store_meta, store_vertical

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("supervmarket.harvest_coordinator")

# Priority ordering: Tech & Marketplaces first, then Supermarkets, then Pharmacies & Specialty
STORE_PRIORITY_ORDER = [
    # Marketplaces / Electro
    "Provincia Compras", "Fravega", "Cetrogar", "On City", "Naldo", "Pardo", "Coppel", "Musimundo",
    "Samsung", "Philips", "Whirlpool", "Moulinex", "Sony", "Oster", "Easy",
    # Supermercados
    "Carrefour", "Coto", "Dia", "Jumbo", "Disco", "Vea", "Masonline", "Josimar", "Toledo", "Cordiez", "TheFoodMarket",
    # Farmacia / Perfumería / Mascotas / Specialty
    "Farmacity", "Farmaplus", "Farmaonline", "Simplicity", "Pigmento", "Puppis", "Catycan", "Natural Life",
    "StyleStore", "Bodegas Bianchi", "LaBarraCCU", "LaBarata", "TonelPrivado", "DePastura", "ArcorEnCasa",
]


class CheckpointManager:
    """Manages atomic checkpoint state using temporary file rename."""

    def __init__(self, filepath: str = ".harvest_checkpoint.json"):
        self.filepath = os.path.abspath(filepath)
        self.state: dict = {"completed_stores": [], "store_counts": {}, "last_updated": ""}
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception as e:
                logger.warning("Failed to load checkpoint file '%s': %s", self.filepath, e)

    def is_completed(self, store_name: str) -> bool:
        return store_name in self.state.get("completed_stores", [])

    def mark_completed(self, store_name: str, count: int):
        if store_name not in self.state["completed_stores"]:
            self.state["completed_stores"].append(store_name)
        self.state["store_counts"][store_name] = count
        self.save()

    def save(self):
        self.state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        tmp_path = f"{self.filepath}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            logger.warning("Failed to save checkpoint: %s", e)


class DatabaseBatchWriter:
    """Dedicated single SQLite writer consuming from asyncio.Queue."""

    def __init__(self, db_path: str, batch_size: int = 250, batch_timeout: float = 1.0, dry_run: bool = False):
        self.db_path = os.path.abspath(db_path)
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.dry_run = dry_run
        self.queue: asyncio.Queue[Optional[HarvesterItem]] = asyncio.Queue(maxsize=5000)
        self.total_written = 0
        self.store_counts: Dict[str, int] = defaultdict(int)
        self.conn: Optional[sqlite3.Connection] = None

    def _open_db(self):
        self.conn = sqlite3.connect(self.db_path, timeout=30.0)
        cur = self.conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.execute("PRAGMA synchronous = NORMAL;")
        cur.execute("PRAGMA busy_timeout = 30000;")
        self.conn.commit()

    async def run(self):
        """Continuously pulls items from the queue and flushes batches atomically."""
        if not self.dry_run:
            self._open_db()

        buffer: List[HarvesterItem] = []
        last_flush = time.time()

        try:
            while True:
                try:
                    # Wait for next item with timeout
                    timeout = max(0.1, self.batch_timeout - (time.time() - last_flush))
                    item = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    item = None

                if item is None:
                    # Check if sentinel (None explicitly placed to shutdown) or timeout
                    if buffer:
                        self._flush_batch(buffer)
                        buffer.clear()
                        last_flush = time.time()
                    continue

                buffer.append(item)
                if len(buffer) >= self.batch_size:
                    self._flush_batch(buffer)
                    buffer.clear()
                    last_flush = time.time()

        except asyncio.CancelledError:
            # Drain remaining items in queue on cancellation
            logger.info("Database writer received cancellation. Flushing remaining buffer...")
            while not self.queue.empty():
                try:
                    rem = self.queue.get_nowait()
                    if rem is not None:
                        buffer.append(rem)
                except asyncio.QueueEmpty:
                    break
            if buffer:
                self._flush_batch(buffer)
        finally:
            if self.conn:
                self.conn.close()
                self.conn = None

    def _flush_batch(self, batch: List[HarvesterItem]):
        if not batch:
            return
        if self.dry_run:
            for it in batch:
                self.total_written += 1
                self.store_counts[it["store_name"]] += 1
            return

        assert self.conn is not None

        raw_rows = []
        prod_rows = []
        price_rows = []

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        for item in batch:
            store_name = item["store_name"]
            ext_id = item["external_id"]
            ean_raw = item["ean_raw"] or ""
            title = item["title_raw"] or "Producto"
            brand = item["brand_raw"] or "Genérico"
            categories = item["categories_raw"] or ""
            link = item["link_raw"] or ""
            image = item["image_raw"] or ""
            price = float(item["price_raw"])
            list_price = float(item["list_price_raw"])
            stock = int(item["stock_raw"])
            seller_id = str(item["seller_id_raw"] or "1")
            raw_json = item["raw_json"]

            # Defense-in-depth price sanity
            if price <= 0:
                stock = 0

            # Defense-in-depth link check
            meta = get_store_meta(store_name)
            if link and not link.startswith("http"):
                dom = meta.get("dominio", "") if meta else ""
                link = f"{dom.rstrip('/')}/{link.lstrip('/')}"

            # Calculate discount
            discount = 0.0
            if list_price > price > 0:
                discount = round(((list_price - price) / list_price) * 100.0, 2)

            resolved_ean = resolve_product_ean(store_name, ext_id, ean_raw)
            v_type = meta.get("vertical", "supermarket") if meta else "supermarket"

            # 1. raw_catalog row
            raw_rows.append((
                store_name, ext_id, ean_raw, title, brand, categories,
                link, image, price, list_price, stock, seller_id, raw_json, now_str
            ))

            # 2. productos row (preserves categoria_normalizada via ON CONFLICT DO UPDATE)
            # Try model extraction
            model_extracted = ""
            try:
                model_extracted = extract_canonical_model({}, {}, title, brand)[0] or ""
            except Exception:
                model_extracted = ""

            prod_rows.append((
                resolved_ean, title, brand, model_extracted, v_type, image, store_name, categories, now_str
            ))

            # 3. precios row
            price_rows.append((
                resolved_ean, store_name, price, list_price, discount, stock, ext_id, link, now_str, seller_id, v_type
            ))

            self.total_written += 1
            self.store_counts[store_name] += 1

        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE;")

            # Upsert into raw_catalog
            cur.executemany("""
                INSERT INTO raw_catalog (
                    store_name, external_id, ean_raw, title_raw, brand_raw, categories_raw,
                    link_raw, image_raw, price_raw, list_price_raw, stock_raw, seller_id_raw,
                    raw_json, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(store_name, external_id, seller_id_raw) DO UPDATE SET
                    ean_raw = excluded.ean_raw,
                    title_raw = excluded.title_raw,
                    brand_raw = excluded.brand_raw,
                    categories_raw = excluded.categories_raw,
                    link_raw = excluded.link_raw,
                    image_raw = excluded.image_raw,
                    price_raw = excluded.price_raw,
                    list_price_raw = excluded.list_price_raw,
                    stock_raw = excluded.stock_raw,
                    raw_json = excluded.raw_json,
                    scraped_at = excluded.scraped_at;
            """, raw_rows)

            # Upsert into productos (NEVER overwrites or resets categoria_normalizada)
            cur.executemany("""
                INSERT INTO productos (
                    ean, nombre, marca, modelo, tipo, imagen, supermercado_origen, categorias, actualizado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ean) DO UPDATE SET
                    nombre = excluded.nombre,
                    marca = excluded.marca,
                    modelo = CASE WHEN excluded.modelo != '' THEN excluded.modelo ELSE productos.modelo END,
                    imagen = CASE WHEN excluded.imagen != '' THEN excluded.imagen ELSE productos.imagen END,
                    categorias = excluded.categorias,
                    actualizado = excluded.actualizado;
            """, prod_rows)

            # Upsert into precios (Winning In-Stock Offer Invariant: 0-stock never overwrites in-stock)
            cur.executemany("""
                INSERT INTO precios (
                    ean, supermercado, precio_venta, precio_lista, descuento,
                    stock, internal_id, link, fecha, seller_id, store_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ean, supermercado) DO UPDATE SET
                    precio_venta = CASE 
                        WHEN excluded.stock > 0 AND (precios.stock <= 0 OR excluded.precio_venta < precios.precio_venta) THEN excluded.precio_venta
                        WHEN precios.stock <= 0 AND excluded.stock <= 0 AND excluded.precio_venta > 0 THEN excluded.precio_venta
                        ELSE precios.precio_venta END,
                    precio_lista = CASE 
                        WHEN excluded.stock > 0 AND (precios.stock <= 0 OR excluded.precio_venta < precios.precio_venta) THEN excluded.precio_lista
                        ELSE precios.precio_lista END,
                    descuento = CASE 
                        WHEN excluded.stock > 0 AND (precios.stock <= 0 OR excluded.precio_venta < precios.precio_venta) THEN excluded.descuento
                        ELSE precios.descuento END,
                    stock = CASE 
                        WHEN excluded.stock > 0 AND (precios.stock <= 0 OR excluded.precio_venta < precios.precio_venta) THEN excluded.stock
                        WHEN precios.stock <= 0 AND excluded.stock > 0 THEN excluded.stock
                        ELSE precios.stock END,
                    internal_id = CASE 
                        WHEN excluded.stock > 0 AND (precios.stock <= 0 OR excluded.precio_venta < precios.precio_venta) THEN excluded.internal_id
                        ELSE precios.internal_id END,
                    link = CASE 
                        WHEN excluded.stock > 0 AND (precios.stock <= 0 OR excluded.precio_venta < precios.precio_venta) THEN excluded.link
                        ELSE precios.link END,
                    fecha = excluded.fecha,
                    seller_id = CASE 
                        WHEN excluded.stock > 0 AND (precios.stock <= 0 OR excluded.precio_venta < precios.precio_venta) THEN excluded.seller_id
                        ELSE precios.seller_id END,
                    store_type = excluded.store_type;
            """, price_rows)

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error("Error executing database batch commit (%d items): %s", len(batch), e)
            raise


class ProgressReporter:
    """Standard-library telemetry dashboard with periodic log lines."""

    def __init__(self, total_stores: int):
        self.total_stores = total_stores
        self.completed_stores = 0
        self.start_time = time.time()
        self.last_report_time = 0.0

    def report(self, current_store: str, store_items: int, total_items: int, force: bool = False):
        now = time.time()
        if not force and (now - self.last_report_time) < 10.0:
            return
        self.last_report_time = now

        elapsed = max(1.0, now - self.start_time)
        rate = total_items / elapsed
        logger.info(
            "PROGRESS [%d/%d stores] Current: %s (+%d items) | Total Ingresados: %d items | Rate: %.1f items/s | Elapsed: %.1fs",
            self.completed_stores, self.total_stores, current_store, store_items, total_items, rate, elapsed
        )


async def store_worker(
    store_name: str,
    writer_queue: asyncio.Queue,
    checkpoint: CheckpointManager,
    reporter: ProgressReporter,
    limit_per_store: Optional[int] = None,
    seeds_only: bool = False,
    categories_only: bool = False,
    include_sitemap: bool = True,
    stop_event: Optional[asyncio.Event] = None,
):
    """Pulls items from harvest_store and enqueues them into writer_queue."""
    if stop_event and stop_event.is_set():
        return

    logger.info(">>> Starting harvesting for store: %s", store_name)
    store_count = 0
    start_store_time = time.time()

    try:
        async for item in harvest_store(
            store_key=store_name,
            max_items=limit_per_store,
            seeds_only=seeds_only,
            categories_only=categories_only,
            include_sitemap=include_sitemap,
        ):
            if stop_event and stop_event.is_set():
                break

            await writer_queue.put(item)
            store_count += 1
            if store_count % 100 == 0:
                reporter.report(store_name, store_count, store_count, force=False)

        checkpoint.mark_completed(store_name, store_count)
        reporter.completed_stores += 1
        elapsed = time.time() - start_store_time
        logger.info(
            "<<< Finished %s: %d items harvested in %.1fs (%.1f items/s)",
            store_name, store_count, elapsed, store_count / max(0.1, elapsed)
        )
    except Exception as e:
        logger.error("Exception during harvest of %s: %s", store_name, e, exc_info=True)


async def main_async(args):
    # Determine target stores
    target_stores: List[str] = []
    if args.stores:
        for s in args.stores.split(","):
            s_clean = s.strip()
            if s_clean:
                target_stores.append(s_clean)
    else:
        # Build prioritized list from STORE_REGISTRY
        registered_keys = set(STORE_REGISTRY.keys())
        for s in STORE_PRIORITY_ORDER:
            if s in registered_keys and s not in target_stores:
                target_stores.append(s)
        for s in registered_keys:
            if s not in target_stores:
                target_stores.append(s)

    # Filter by vertical if requested
    if args.vertical:
        target_stores = [
            s for s in target_stores
            if store_vertical(s).lower() == args.vertical.lower()
        ]

    # Initialize Checkpoint
    checkpoint = CheckpointManager(args.checkpoint_file)
    if args.resume:
        before_count = len(target_stores)
        target_stores = [s for s in target_stores if not checkpoint.is_completed(s)]
        logger.info("Resuming sweep: %d stores already completed. %d stores remaining.", before_count - len(target_stores), len(target_stores))

    if not target_stores:
        logger.info("No stores to harvest. Everything is up to date!")
        return

    logger.info("Ready to harvest %d stores with %d workers (batch_size=%d, db=%s)",
                len(target_stores), args.workers, args.batch_size, args.db_path)

    # Initialize Writer & Progress Reporter
    writer = DatabaseBatchWriter(
        db_path=args.db_path,
        batch_size=args.batch_size,
        batch_timeout=args.batch_timeout,
        dry_run=args.dry_run,
    )
    writer_task = asyncio.create_task(writer.run())
    reporter = ProgressReporter(len(target_stores))

    # Signal Handling
    stop_event = asyncio.Event()

    def handle_signal():
        logger.warning("Signal received! Initiating graceful shutdown and queue flush...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            # Windows fallback
            pass

    # Concurrency Semaphore for Stores
    store_sem = asyncio.Semaphore(args.workers)

    async def sem_worker(st_name: str):
        async with store_sem:
            await store_worker(
                store_name=st_name,
                writer_queue=writer.queue,
                checkpoint=checkpoint,
                reporter=reporter,
                limit_per_store=args.limit_per_store,
                seeds_only=args.seeds_only,
                categories_only=args.categories_only,
                include_sitemap=not args.no_sitemap,
                stop_event=stop_event,
            )

    worker_tasks = [asyncio.create_task(sem_worker(st)) for st in target_stores]
    await asyncio.gather(*worker_tasks, return_exceptions=True)

    # Wait for queue to drain
    logger.info("All store harvesting tasks finished. Waiting for database writer to drain...")
    while not writer.queue.empty():
        await asyncio.sleep(0.2)

    # Cancel writer task to trigger buffer flush
    writer_task.cancel()
    try:
        await writer_task
    except asyncio.CancelledError:
        pass

    reporter.report("ALL_COMPLETED", 0, writer.total_written, force=True)
    logger.info("Harvest complete! Total items committed to database: %d across %d stores.",
                writer.total_written, len(writer.store_counts))


def main():
    parser = argparse.ArgumentParser(description="Multi-store harvesting CLI coordinator with WAL batch writer.")
    parser.add_argument("--stores", default="", help="Comma-separated store keys to harvest.")
    parser.add_argument("--vertical", default="", help="Filter by vertical: supermarket, electro, marketplace, pharmacy, specialty.")
    parser.add_argument("--seeds-only", action="store_true", help="Harvest only via 100 departmental query seeds.")
    parser.add_argument("--categories-only", action="store_true", help="Harvest only via category tree.")
    parser.add_argument("--no-sitemap", action="store_true", help="Disable sitemap discovery.")
    parser.add_argument("--limit-per-store", type=int, default=None, help="Maximum items per store.")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent store workers (default: 6).")
    parser.add_argument("--db-path", default="supervmarket.db", help="Path to SQLite database.")
    parser.add_argument("--batch-size", type=int, default=250, help="Batch commit transaction size.")
    parser.add_argument("--batch-timeout", type=float, default=1.0, help="Flush timeout in seconds.")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint, skipping finished stores.")
    parser.add_argument("--checkpoint-file", default=".harvest_checkpoint.json", help="Path to checkpoint file.")
    parser.add_argument("--dry-run", action="store_true", help="Execute without writing to database.")
    parser.add_argument("--verbose", action="store_true", help="Verbose debug logging.")

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
