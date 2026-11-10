import sqlite3
import concurrent.futures
import time

conn = sqlite3.connect("supervmarket.db", check_same_thread=False)

def query(i):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM productos")
    res = cur.fetchone()[0]
    cur.close()
    return res

t0 = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
    futures = [ex.submit(query, i) for i in range(10)]
    results = [f.result() for f in futures]
print("Pure sqlite3 results:", results, f"in {(time.perf_counter()-t0)*1000:.1f}ms")
