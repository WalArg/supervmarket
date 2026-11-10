#!/usr/bin/env python3
"""scripts/reconcile_precios_from_raw.py

Reconciles active in-stock offers from raw_catalog into precios.
Ensures that whenever raw_catalog has an active offer (stock > 0 and price > 0),
it is never masked by a 0-stock seller listing in precios.
"""

import os
import sys
import time
import sqlite3

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api._lib.harvester import resolve_product_ean
from api._lib.stores import get_store_meta

def main():
    db_path = "supervmarket.db"
    conn = sqlite3.connect(db_path, timeout=30.0)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")

    print("Querying in-stock items from raw_catalog...")
    cur.execute("""
        SELECT store_name, external_id, ean_raw, price_raw, list_price_raw, stock_raw, seller_id_raw, link_raw
        FROM raw_catalog
        WHERE stock_raw > 0 AND price_raw > 0
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} in-stock items in raw_catalog.")

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    batch_size = 2000
    price_batch = []
    updated_count = 0

    t0 = time.time()
    for row in rows:
        store_name, ext_id, ean_raw, price, list_price, stock, seller_id, link = row
        resolved_ean = resolve_product_ean(store_name, ext_id, ean_raw)
        meta = get_store_meta(store_name)
        v_type = meta.get("vertical", "supermarket") if meta else "supermarket"
        if link and not link.startswith("http"):
            dom = meta.get("dominio", "") if meta else ""
            link = f"{dom.rstrip('/')}/{link.lstrip('/')}"
        discount = 0.0
        if list_price > price > 0:
            discount = round(((list_price - price) / list_price) * 100.0, 2)

        price_batch.append((
            resolved_ean, store_name, price, list_price, discount,
            stock, ext_id, link, now_str, str(seller_id or "1"), v_type
        ))

        if len(price_batch) >= batch_size:
            cur.executemany("""
                INSERT INTO precios (
                    ean, supermercado, precio_venta, precio_lista, descuento,
                    stock, internal_id, link, fecha, seller_id, store_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ean, supermercado) DO UPDATE SET
                    precio_venta = CASE 
                        WHEN excluded.stock > 0 AND (precios.stock <= 0 OR excluded.precio_venta < precios.precio_venta) THEN excluded.precio_venta
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
            """, price_batch)
            conn.commit()
            updated_count += len(price_batch)
            price_batch.clear()
            if updated_count % 20000 == 0:
                print(f"Processed {updated_count}/{len(rows)} in {time.time()-t0:.1f}s...")

    if price_batch:
        cur.executemany("""
            INSERT INTO precios (
                ean, supermercado, precio_venta, precio_lista, descuento,
                stock, internal_id, link, fecha, seller_id, store_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ean, supermercado) DO UPDATE SET
                precio_venta = CASE 
                    WHEN excluded.stock > 0 AND (precios.stock <= 0 OR excluded.precio_venta < precios.precio_venta) THEN excluded.precio_venta
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
        """, price_batch)
        conn.commit()
        updated_count += len(price_batch)

    print(f"Reconciliation complete! Processed {updated_count} in-stock items in {time.time()-t0:.1f}s.")

if __name__ == "__main__":
    main()
