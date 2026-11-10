#!/usr/bin/env python3
"""scripts/migrate_raw_catalog.py

Database migration for Milestone 1:
1. Configures SQLite WAL mode, synchronous=NORMAL, and busy_timeout=30000.
2. Creates the `raw_catalog` table with complete raw payload fields, scraped_at,
   and UNIQUE(store_name, external_id, seller_id_raw) constraint.
3. Creates indexes on raw_catalog: idx_raw_catalog_store, idx_raw_catalog_ean, idx_raw_catalog_ext.
4. Creates performance/normalization indexes:
   - idx_productos_cat_norm ON productos(categoria_normalizada)
   - idx_precios_ean_stock ON precios(ean, precio_venta) WHERE stock > 0
"""

import argparse
import os
import sqlite3
import sys

RAW_CATALOG_DDL = """
CREATE TABLE IF NOT EXISTS raw_catalog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name      TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    ean_raw         TEXT,
    title_raw       TEXT NOT NULL,
    brand_raw       TEXT,
    categories_raw  TEXT,
    link_raw        TEXT NOT NULL,
    image_raw       TEXT,
    price_raw       REAL NOT NULL,
    list_price_raw  REAL,
    stock_raw       INTEGER DEFAULT 1,
    seller_id_raw   TEXT DEFAULT '1',
    raw_json        TEXT NOT NULL,
    scraped_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (store_name, external_id, seller_id_raw)
);
"""

INDEXES_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_raw_catalog_store ON raw_catalog(store_name);",
    "CREATE INDEX IF NOT EXISTS idx_raw_catalog_ean ON raw_catalog(ean_raw);",
    "CREATE INDEX IF NOT EXISTS idx_raw_catalog_ext ON raw_catalog(external_id);",
    "CREATE INDEX IF NOT EXISTS idx_productos_cat_norm ON productos(categoria_normalizada);",
    "CREATE INDEX IF NOT EXISTS idx_precios_ean_stock ON precios(ean, precio_venta) WHERE stock > 0;",
]


def run_migration(db_path: str = "supervmarket.db") -> dict:
    abs_path = os.path.abspath(db_path)
    if not os.path.exists(abs_path):
        print(f"Warning: Database file '{abs_path}' does not exist yet. It will be initialized.")

    conn = sqlite3.connect(abs_path, timeout=30.0)
    try:
        cursor = conn.cursor()

        # Step 1: WAL & Performance Pragmas
        cursor.execute("PRAGMA journal_mode = WAL;")
        journal_mode = cursor.fetchone()[0]

        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 30000;")

        # Step 2: DDL raw_catalog
        cursor.execute(RAW_CATALOG_DDL)

        # Step 3: Indexes
        for idx_sql in INDEXES_DDL:
            cursor.execute(idx_sql)

        conn.commit()

        # Verify applied pragmas
        cursor.execute("PRAGMA synchronous;")
        sync_mode = cursor.fetchone()[0]
        cursor.execute("PRAGMA busy_timeout;")
        b_timeout = cursor.fetchone()[0]

        # Verify raw_catalog columns
        cursor.execute("PRAGMA table_info(raw_catalog);")
        columns = [row[1] for row in cursor.fetchall()]

        # Verify indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = [row[0] for row in cursor.fetchall()]

        return {
            "status": "success",
            "db_path": abs_path,
            "journal_mode": journal_mode,
            "synchronous": sync_mode,
            "busy_timeout": b_timeout,
            "raw_catalog_columns": columns,
            "indexes": indexes,
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite database to support raw_catalog and WAL mode.")
    parser.add_argument("--db", "--db-path", dest="db_path", default="supervmarket.db", help="Path to SQLite database file.")
    args = parser.parse_args()

    result = run_migration(args.db_path)
    print("=" * 60)
    print("SuperVmarket Migration: raw_catalog & WAL Pragmas")
    print("=" * 60)
    print(f"Database:     {result['db_path']}")
    print(f"Journal Mode: {result['journal_mode']}")
    print(f"Synchronous:  {result['synchronous']}")
    print(f"Busy Timeout: {result['busy_timeout']} ms")
    print(f"Columns:      {len(result['raw_catalog_columns'])} columns in raw_catalog")
    print(f"Indexes:      {', '.join(result['indexes'])}")
    print("Migration completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
