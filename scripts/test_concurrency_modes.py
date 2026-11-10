import asyncio
import concurrent.futures
import os
import sys
import time

sys.stdout.reconfigure(line_buffering=True)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))
from _lib import db

# Mode A: Async concurrency (20 concurrent coroutines, 200 queries total)
async def test_async_concurrency():
    print("\n--- Test A: Async Concurrency (20 concurrent coroutines, 200 queries) ---")
    queries = ["tv", "celular", "notebook", "heladera", "lavarropas", "leche", "arroz", "fideos"]
    sem = asyncio.Semaphore(20)

    latencies = []
    async def worker(q):
        async with sem:
            t0 = time.perf_counter()
            res = await db.search_grouped(q, limit=10)
            dt = (time.perf_counter() - t0) * 1000
            latencies.append(dt)
            return len(res)

    tasks = [worker(queries[i % len(queries)]) for i in range(200)]
    t0_all = time.perf_counter()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = (time.perf_counter() - t0_all) * 1000

    errors = [r for r in results if isinstance(r, Exception)]
    mean_lat = sum(latencies) / len(latencies) if latencies else 0
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0

    print(f"Total time: {total_time:.1f}ms")
    print(f"Mean latency: {mean_lat:.2f}ms")
    print(f"P95 latency: {p95:.2f}ms")
    print(f"Errors: {len(errors)}")
    if errors:
        print("Sample error:", errors[0])

asyncio.run(test_async_concurrency())
