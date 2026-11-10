import asyncio
import concurrent.futures
import threading
import sqlite3
import os
import sys
import time

sys.stdout.reconfigure(line_buffering=True)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))
from _lib import db

# Test: What if each thread opens its own connection or uses a Lock?
# Let's see how fast 20 threads running 200 queries is with thread-local connections:
local_storage = threading.local()

def get_thread_conn():
    if not hasattr(local_storage, "conn"):
        conn = sqlite3.connect("supervmarket.db", timeout=30)
        conn.row_factory = sqlite3.Row
        conn.create_function("unaccent", 1, db._py_unaccent)
        local_storage.conn = conn
    return local_storage.conn

# Let's benchmark 20 threads executing 200 random queries with thread-local connections:
queries = [
    "tv", "smart tv", "televisor", "celular", "celulares", "notebook",
    "laptop", "heladera", "lavarropas", "soporte tv", "rack tv", "funda celular"
]

import random
query_list = [random.choice(queries) for _ in range(200)]

def run_query(q):
    t0 = time.perf_counter()
    conn = get_thread_conn()
    intent = db.detect_search_intent(q)
    # Execute query
    cur = conn.execute(
        "SELECT p.ean, MIN(pr.precio_venta) AS best, COUNT(DISTINCT pr.supermercado) AS stores_cnt "
        "FROM productos p JOIN precios pr ON pr.ean = p.ean "
        "WHERE p.categoria_normalizada = ? AND pr.stock > 0 "
        "GROUP BY p.ean ORDER BY best ASC LIMIT 10",
        (intent,)
    )
    rows = cur.fetchall()
    cur.close()
    dt = (time.perf_counter() - t0) * 1000
    return dt

t0 = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
    futures = [ex.submit(run_query, q) for q in query_list]
    lats = [f.result() for f in futures]
total_dt = (time.perf_counter() - t0) * 1000

print(f"Thread-local SQLite: 20 threads, 200 queries in {total_dt:.1f}ms")
print(f"Mean latency: {sum(lats)/len(lats):.2f}ms")
print(f"P95 latency: {sorted(lats)[int(len(lats)*0.95)]:.2f}ms")
