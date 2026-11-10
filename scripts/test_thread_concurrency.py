import asyncio
import concurrent.futures
import os
import sys
import time

sys.stdout.reconfigure(line_buffering=True)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))
from _lib import db

print("Warming up db in main thread first...")
asyncio.run(db.search_grouped("calentamiento", limit=1))
print("Warmup complete. Now launching 20 threads for 200 queries...")

sample_queries = ["tv", "celular", "notebook", "heladera", "leche", "arroz"]

def run_one(i):
    q = sample_queries[i % len(sample_queries)]
    t0 = time.perf_counter()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        res = loop.run_until_complete(db.search_grouped(q, limit=10))
        dt = (time.perf_counter() - t0) * 1000
        return (dt, None, len(res))
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return (dt, e, 0)
    finally:
        loop.close()

t0_all = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(run_one, i) for i in range(200)]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

total_ms = (time.perf_counter() - t0_all) * 1000
lats = [r[0] for r in results]
errs = [r[1] for r in results if r[1] is not None]
print(f"Executed 200 queries in {total_ms:.1f}ms")
print(f"Mean latency: {sum(lats)/len(lats):.2f}ms")
print(f"Max latency: {max(lats):.2f}ms")
print(f"Errors count: {len(errs)}")
if errs:
    print("Sample error:", errs[0])
