import asyncio
import os
import sys
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))
from _lib import db

async def measure_each():
    queries = ["tv", "smart tv", "celular", "notebook", "heladera", "lavarropas", "leche", "arroz", "fideos"]
    for q in queries:
        t0 = time.perf_counter()
        res = await db.search_grouped(q, limit=10)
        dt = (time.perf_counter() - t0) * 1000
        print(f"Query '{q:<15}': {dt:.2f}ms (count={len(res)})")

asyncio.run(measure_each())
