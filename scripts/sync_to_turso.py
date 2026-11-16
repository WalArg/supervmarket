"""scripts/sync_to_turso.py

Sincronizador inicial del catálogo local limpio (productos y precios)
hacia la base de datos Turso / LibSQL en la nube.
Omite la tabla raw_catalog de 30GB para mantener la base ligera (~250MB).
"""

import os
import sys
import time
import sqlite3
import asyncio
import httpx

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "https://supervmarket-walarg.aws-sa-east-1.turso.io")
if TURSO_URL.startswith("libsql://"):
    TURSO_URL = TURSO_URL.replace("libsql://", "https://")
TURSO_TOKEN = os.environ.get(
    "TURSO_AUTH_TOKEN",
    "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTQ3OTcxMzMsImlkIjoiMDFhMWUyM2UtNzkwMS03ZGE2LWJmOGMtMjhlNzY5OGY4ZDkyIiwia2lkIjoiRkNKbFZJM05fdzBFZG51RU1zWmp1eWxZdW5nMVdHT25lWDMzcmNISV9JcyIsInJpZCI6IjIyMzYxMDM5LWJiMDMtNDliNi1hMzFkLTJiYzIyNGU5NzZiZCJ9.qrswQjXyAlAugwuSfbJ4HHeMEyVUnXaew2bpil8S7OzWQ7gmYPnhT_x-ZJKPChLsAaXsLlJVZfS-vnyCjISuDA"
)

def _to_arg(val):
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

async def send_batch(client: httpx.AsyncClient, statements: list, retries: int = 3) -> bool:
    pipeline_url = f"{TURSO_URL.rstrip('/')}/v2/pipeline"
    payload = {
        "requests": [{"type": "execute", "stmt": s} for s in statements] + [{"type": "close"}]
    }
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
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
                print(f"[Error batch] {e}")
            await asyncio.sleep(1.0 * (attempt + 1))
    return False

async def sync_data(limit_products: int = 25000):
    db_path = os.path.join(ROOT_DIR, "supervmarket.db")
    if not os.path.exists(db_path):
        print(f"No existe {db_path}")
        return

    print(f"Abriendo base local: {db_path}")
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Seleccionar productos prioritarios (supermercados y productos con precios activos)
    print("Leyendo productos prioritarios...")
    cur.execute(f"""
        SELECT p.ean, p.nombre, p.marca, p.modelo, p.tipo, p.imagen, p.supermercado_origen, 
               p.categorias, p.categoria_normalizada, p.actualizado, p.search_text
        FROM productos p
        WHERE p.ean IN (SELECT DISTINCT ean FROM precios WHERE precio_venta > 0)
        ORDER BY (CASE WHEN p.tipo = 'supermarket' THEN 1 ELSE 2 END), p.ean
        LIMIT {limit_products}
    """)
    prod_rows = cur.fetchall()
    print(f"Total productos a migrar: {len(prod_rows):,}")

    eans_set = set(r[0] for r in prod_rows)
    ph = ",".join("?" * len(eans_set))
    print("Leyendo precios asociados...")
    cur.execute(f"""
        SELECT ean, supermercado, precio_venta, precio_lista, descuento, precio_por_unidad, 
               unidad_medida, stock, internal_id, link, fecha, promo_etiqueta, promo_tipo, 
               promo_min_qty, precio_promo_unit, requiere_club, seller_id, store_type
        FROM precios
        WHERE ean IN ({ph}) AND precio_venta > 0
    """, list(eans_set))
    precio_rows = cur.fetchall()
    print(f"Total precios a migrar: {len(precio_rows):,}")
    con.close()

    limits = httpx.Limits(max_connections=30, max_keepalive_connections=15, keepalive_expiry=30.0)
    async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        # 1. Subir productos en lotes de 60
        BATCH_SIZE = 60
        print(f"\nSubiendo productos a Turso ({len(prod_rows)} ítems en lotes de {BATCH_SIZE})...")
        t0 = time.time()
        uploaded_p = 0
        sql_prod = (
            "INSERT OR REPLACE INTO productos (ean, nombre, marca, modelo, tipo, imagen, "
            "supermercado_origen, categorias, categoria_normalizada, actualizado, search_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for i in range(0, len(prod_rows), BATCH_SIZE):
            chunk = prod_rows[i:i + BATCH_SIZE]
            stmts = []
            for r in chunk:
                stmts.append({
                    "sql": sql_prod,
                    "args": [_to_arg(v) for v in r]
                })
            ok = await send_batch(client, stmts)
            if ok:
                uploaded_p += len(chunk)
                if uploaded_p % 600 == 0 or uploaded_p == len(prod_rows):
                    rate = uploaded_p / max(0.1, time.time() - t0)
                    print(f"  Productos: {uploaded_p:,}/{len(prod_rows):,} ({rate:.1f} prods/seg)")

        # 2. Subir precios en lotes de 80
        P_BATCH = 80
        print(f"\nSubiendo precios a Turso ({len(precio_rows)} filas en lotes de {P_BATCH})...")
        t0 = time.time()
        uploaded_pr = 0
        sql_pr = (
            "INSERT OR REPLACE INTO precios (ean, supermercado, precio_venta, precio_lista, "
            "descuento, precio_por_unidad, unidad_medida, stock, internal_id, link, fecha, "
            "promo_etiqueta, promo_tipo, promo_min_qty, precio_promo_unit, requiere_club, "
            "seller_id, store_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for i in range(0, len(precio_rows), P_BATCH):
            chunk = precio_rows[i:i + P_BATCH]
            stmts = []
            for r in chunk:
                stmts.append({
                    "sql": sql_pr,
                    "args": [_to_arg(v) for v in r]
                })
            ok = await send_batch(client, stmts)
            if ok:
                uploaded_pr += len(chunk)
                if uploaded_pr % 800 == 0 or uploaded_pr == len(precio_rows):
                    rate = uploaded_pr / max(0.1, time.time() - t0)
                    print(f"  Precios: {uploaded_pr:,}/{len(precio_rows):,} ({rate:.1f} precios/seg)")

    print(f"\n¡Sincronización completada! {uploaded_p:,} productos y {uploaded_pr:,} precios en Turso.")

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15000
    asyncio.run(sync_data(n))
