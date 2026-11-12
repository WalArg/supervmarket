#!/usr/bin/env python3
"""scripts/enhance_data_quality.py

Comprehensive Data Quality & Comparison Enhancement Pipeline:
1. Saneamiento de Precios & Descuentos Fantasma:
   - Identifies inflated list prices (e.g. Cencosud 82.64x artifact or typos).
   - Resets fake discounts (>80% without verified promo tag) to real regular prices.
   - Enforces stock=0 on zero/negative prices.
2. Canonical Image Enrichment:
   - For every canonical EAN, selects the highest-quality verified image from official/reputable CDNs
     (Samsung, Philips, Carrefour, Jumbo, Farmaonline) replacing broken or low-quality seller thumbnails.
3. Unit Price Standardization:
   - Extracts unit of measure (kg, g, lt, ml, u, lavados) and calculates price_per_unit ($/kg, $/lt).
   - Enables genuine cross-store price-per-unit comparisons.
4. Entity Resolution & Canonical Repointing:
   - Runs catalog_normalizer to merge non-EAN items into canonical GS1 products.
   - Classifies 100% of products into the 19 canonical categories.
"""

import logging
import os
import re
import sqlite3
import sys
import time
from typing import Dict, List, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.catalog_normalizer import normalize_catalog
from api._lib.parsers import extraer_unidad_titulo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("supervmarket.enhance_data")

# Reputable image domains in order of trust/quality
TRUSTED_IMAGE_PRIORITY = [
    "shop.samsung.com.ar",
    "tienda.philips.com.ar",
    "whirlpool.com.ar",
    "carrefourar.vteximg.com.br",
    "jumboargentina.vteximg.com.br",
    "farmacityar.vteximg.com.br",
    "farmaonline.vteximg.com.br",
    "fravega.vteximg.com.br",
    "arcencohogar.vteximg.com.br",
    "static.cotodigital3.com.ar",
    "baproar.vteximg.com.br",
    "coppelar.vteximg.com.br",
]


def sanitize_ghost_discounts(conn: sqlite3.Connection) -> Dict[str, int]:
    """Identifies and fixes inflated list prices and fake discounts."""
    cur = conn.cursor()
    logger.info("Sanitizing ghost discounts and inflated list prices...")
    
    # 1. Zero/negative price protection: force stock = 0
    cur.execute("""
        UPDATE precios
        SET stock = 0
        WHERE precio_venta <= 0 AND stock > 0;
    """)
    zero_stock_fixed = cur.rowcount

    # 2. Fix inflated list prices where precio_lista > precio_venta * 3
    # If list price is inflated by ~82.64 (Cencosud VAT artifact) or > 3x without a promo tag,
    # reset precio_lista = precio_venta, descuento = 0.0
    cur.execute("""
        UPDATE precios
        SET precio_lista = precio_venta,
            descuento = 0.0
        WHERE (precio_lista > precio_venta * 3.0 OR descuento > 80.0)
          AND (promo_etiqueta IS NULL OR promo_etiqueta = '' OR promo_etiqueta NOT LIKE '%2x1%');
    """)
    ghost_discounts_fixed = cur.rowcount

    # 3. Recalculate discounts for any remaining legitimate price differences
    cur.execute("""
        UPDATE precios
        SET descuento = ROUND(((precio_lista - precio_venta) / precio_lista) * 100.0, 1)
        WHERE precio_lista > precio_venta AND precio_venta > 0 AND descuento <= 80.0;
    """)
    recalculated = cur.rowcount

    conn.commit()
    logger.info(
        "Price Sanitization Complete: %d zero-price offers forced to stock=0 | %d ghost discounts eliminated | %d legitimate discounts recalculated",
        zero_stock_fixed, ghost_discounts_fixed, recalculated
    )
    return {
        "zero_stock_fixed": zero_stock_fixed,
        "ghost_discounts_fixed": ghost_discounts_fixed,
        "recalculated_discounts": recalculated,
    }


def enrich_canonical_images(conn: sqlite3.Connection) -> int:
    """Selects the best available verified image for every product from raw_catalog offers."""
    cur = conn.cursor()
    logger.info("Enriching canonical product images from verified store sources...")

    # Query trusted store catalogs using idx_raw_catalog_store index
    cur.execute("""
        SELECT ean_raw, image_raw, store_name
        FROM raw_catalog
        WHERE store_name IN ('Samsung', 'Philips', 'Whirlpool', 'Carrefour', 'Jumbo', 'Disco', 'Vea', 'Farmacity', 'Farmaonline', 'Frávega', 'Coto')
          AND image_raw IS NOT NULL AND image_raw != ''
    """)
    rows = cur.fetchall()

    ean_candidates: Dict[str, List[Tuple[int, str]]] = {}
    for ean, img, store in rows:
        if not img or not img.startswith("http"):
            continue
        if "ids/676579" in img or "ids/607590" in img or "placeholder" in img:
            continue
        # Score image by source domain
        score = 99
        for idx, dom in enumerate(TRUSTED_IMAGE_PRIORITY):
            if dom in img:
                score = idx
                break
        if ean not in ean_candidates:
            ean_candidates[ean] = []
        ean_candidates[ean].append((score, img))

    updates = []
    for ean, cand_list in ean_candidates.items():
        cand_list.sort(key=lambda x: x[0])
        best_img = cand_list[0][1]
        updates.append((best_img, ean))

    CHUNK_SIZE = 5000
    for i in range(0, len(updates), CHUNK_SIZE):
        chunk = updates[i : i + CHUNK_SIZE]
        cur.executemany("UPDATE productos SET imagen = ? WHERE ean = ?", chunk)
    conn.commit()

    logger.info("Canonical Image Enrichment Complete: Updated %d products with trusted images", len(updates))
    return len(updates)


def standardize_unit_prices(conn: sqlite3.Connection) -> int:
    """Populates precio_por_unidad and unidad_medida across all grocery/consumable offers."""
    cur = conn.cursor()
    logger.info("Standardizing unit prices ($/kg, $/lt, $/u)...")

    cur.execute("""
        SELECT p.ean, p.supermercado, p.precio_venta, pr.nombre
        FROM precios p
        JOIN productos pr ON p.ean = pr.ean
        WHERE p.precio_venta > 0 AND (p.unidad_medida IS NULL OR p.unidad_medida = '')
    """)
    rows = cur.fetchall()

    updates = []
    for ean, store, p_venta, nombre in rows:
        if not nombre:
            continue
        qty, unit = extraer_unidad_titulo(nombre)
        if qty > 0 and unit in ("kg", "lt", "g", "ml", "u", "lavados"):
            norm_unit = unit
            unit_price = p_venta / qty
            if unit == "g":
                norm_unit = "kg"
                unit_price = (p_venta / qty) * 1000.0
            elif unit == "ml":
                norm_unit = "lt"
                unit_price = (p_venta / qty) * 1000.0
            
            unit_price = round(unit_price, 2)
            updates.append((unit_price, norm_unit, ean, store))

    CHUNK_SIZE = 5000
    for i in range(0, len(updates), CHUNK_SIZE):
        chunk = updates[i : i + CHUNK_SIZE]
        cur.executemany("""
            UPDATE precios
            SET precio_por_unidad = ?, unidad_medida = ?
            WHERE ean = ? AND supermercado = ?
        """, chunk)
    conn.commit()

    logger.info("Unit Price Standardization Complete: %d offers updated with $/unit metrics", len(updates))
    return len(updates)


def main():
    db_path = os.path.abspath("supervmarket.db")
    logger.info("=================================================================")
    logger.info("STARTING COMPREHENSIVE DATA QUALITY ENHANCEMENT PIPELINE")
    logger.info("Target Database: %s", db_path)
    logger.info("=================================================================")

    t0 = time.perf_counter()
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -64000;")

    # 1. Sanitize Ghost Discounts & Negative Prices
    ghost_stats = sanitize_ghost_discounts(conn)

    # 2. Enrich Canonical Images with Trusted Sources
    images_updated = enrich_canonical_images(conn)

    # 3. Standardize Unit Prices ($/kg, $/lt)
    units_updated = standardize_unit_prices(conn)
    conn.close()

    # 4. Execute Full Catalog Entity Resolution & Canonical Category Classification
    logger.info("Running Global Entity Resolution & Category Normalization...")
    norm_res = normalize_catalog(db_path, dry_run=False)

    # 5. Checkpoint and Optimize SQLite
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_precios_deals ON precios (stock, descuento DESC, precio_venta);")
    conn.commit()
    cur.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    logger.info("WAL Checkpoint: %s", cur.fetchall())
    cur.execute("ANALYZE productos;")
    cur.execute("ANALYZE precios;")
    logger.info("SQLite ANALYZE completed for active query tables.")
    conn.close()

    elapsed = time.perf_counter() - t0
    logger.info("=================================================================")
    logger.info("DATA QUALITY PIPELINE COMPLETED IN %.1fs", elapsed)
    logger.info("  - Ghost Discounts Fixed: %d", ghost_stats["ghost_discounts_fixed"])
    logger.info("  - Canonical Images Enriched: %d", images_updated)
    logger.info("  - Unit Prices Standardized: %d", units_updated)
    logger.info("  - Entities Repointed into Canonical EANs: %d", norm_res["entity_resolution"]["total_repointed"])
    logger.info("  - Categories Normalized (100%%): %d", norm_res["categories_updated"])
    logger.info("=================================================================")


if __name__ == "__main__":
    main()
