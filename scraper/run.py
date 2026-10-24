"""Orquestador del scraper. Corre todos los supermercados (o uno específico) y guarda en la base.

Uso:
    python run.py --from-raw                  # procesa todos los dumps de raw/*.csv en ~2 seg
    python run.py --from-raw --store Jumbo    # procesa solo Jumbo desde raw/
    python run.py --store Carrefour --limit 50 # scrapea solo Carrefour en vivo (50 productos)
    python run.py --limit 100                 # scrapea todas las tiendas en vivo (100 c/u)
"""
import os
import sys
import csv
import json
import glob
import time
import asyncio
import pathlib

# En Windows la consola por defecto usa cp1252 y crashea al imprimir emojis/acentos;
# si crashea antes de db.close(), el hilo de aiosqlite dejaba el proceso colgado.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import Database
from coto import CotoScraper, parse_coto_record
from vtex import VtexScraper, parse_vtex_product

STORES = [
    VtexScraper("Jumbo", "https://www.jumbo.com.ar"),
    VtexScraper("Disco", "https://www.disco.com.ar"),
    VtexScraper("Vea", "https://www.vea.com.ar"),
    VtexScraper("Carrefour", "https://www.carrefour.com.ar"),
    VtexScraper("Dia", "https://diaonline.supermercadosdia.com.ar"),
    VtexScraper("Masonline", "https://www.masonline.com.ar"),
    VtexScraper("Farmacity", "https://www.farmacity.com"),
    VtexScraper("Simplicity", "https://www.simplicity.com.ar"),
    VtexScraper("Farmaonline", "https://www.farmaonline.com"),
    VtexScraper("Farmaplus", "https://www.farmaplus.com.ar"),
    VtexScraper("TheFoodMarket", "https://www.thefoodmarket.com.ar"),
    CotoScraper(),
]

RAW_DIR = pathlib.Path(__file__).resolve().parent.parent / "raw"


def _get_arg(flag: str) -> str | None:
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None


def _get_limit() -> int | None:
    val = _get_arg("--limit")
    if val:
        return int(val)
    env = os.getenv("SCRAPER_LIMIT")
    return int(env) if env else None


def import_from_raw_sync(store_filter: str | None = None):
    """Procesa síncronamente los dumps reales de `raw/*.csv` en menos de 2 segundos."""
    t0 = time.time()
    db = Database()
    if not db.is_sqlite:
        raise RuntimeError("Usar modo async para Postgres")

    import sqlite3
    from db import SCHEMA_SQLITE, SQLITE_MIGRATIONS
    db.conn = sqlite3.connect(db.sqlite_file, timeout=30)
    try:
        db.conn.executescript(SCHEMA_SQLITE)
        for stmt in SQLITE_MIGRATIONS:
            try:
                db.conn.execute(stmt)
            except Exception:
                pass
        db.conn.commit()

        csv.field_size_limit(10**7)
        files = sorted(glob.glob(str(RAW_DIR / "*.csv")))
        if not files:
            print("No se encontraron archivos en raw/*.csv", flush=True)
            return

        total_saved = 0
        for path in files:
            store_name = pathlib.Path(path).stem
            if store_name in ("Easy", "Samsung", "LaBarraCCU", "MercadoLibre"):
                continue
            if store_filter and store_name.lower() != store_filter.lower():
                continue

            t_store = time.time()
            products = []
            with open(path, encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("endpoint") != "product" or row.get("ok") != "True":
                        continue
                    raw = row.get("raw_json") or ""
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue
                    engine = (row.get("engine") or "").lower()
                    url = row.get("url") or ""
                    parsed = None
                    if engine == "vtex":
                        prod_obj = data[0] if isinstance(data, list) and data else data
                        parsed = parse_vtex_product(prod_obj, store_name, fallback_url=url)
                    elif engine == "endeca":
                        parsed = parse_coto_record(data, url=url)
                    if parsed:
                        products.append(parsed)

            if products:
                db._save_sqlite_fast(products)
                promos_count = sum(1 for p in products if p.get("promo_etiqueta"))
                elapsed = time.time() - t_store
                print(
                    f"[{store_name:<12}] OK {len(products):>3} productos | "
                    f"{promos_count:>3} ofertas reales detectadas | {elapsed:.2f}s",
                    flush=True,
                )
                total_saved += len(products)

        print(f"\nTotal importado: {total_saved} productos en {time.time() - t0:.2f}s", flush=True)
    finally:
        db.conn.close()


async def run_one(scraper, db: Database, limit):
    try:
        t0 = time.time()
        products = await scraper.correr(limit=limit)
        if products:
            print(f"[{scraper.nombre}] Guardando {len(products)} en DB...", flush=True)
            await db.save_batch(products)
            print(f"[{scraper.nombre}] OK en {time.time() - t0:.1f}s", flush=True)
    except Exception as e:
        print(f"[{scraper.nombre}] ERROR: {e}", flush=True)


async def main_async(store_filter: str | None = None):
    limit = _get_limit()
    target_stores = [
        s for s in STORES
        if not store_filter or s.nombre.lower() == store_filter.lower()
    ]
    print(
        f"SuperVmarket scraper — {len(target_stores)} tienda(s)"
        + (f" (limite {limit}/tienda)" if limit else ""),
        flush=True,
    )
    start = time.time()

    db = Database()
    await db.connect()
    try:
        await db.init_schema()
        for i in range(0, len(target_stores), 3):
            await asyncio.gather(*(run_one(s, db, limit) for s in target_stores[i:i + 3]))
    finally:
        await db.close()
    print(f"\nTotal: {(time.time() - start):.1f} seg", flush=True)


if __name__ == "__main__":
    store_arg = _get_arg("--store")
    if "--from-raw" in sys.argv:
        import_from_raw_sync(store_filter=store_arg)
    else:
        asyncio.run(main_async(store_filter=store_arg))
