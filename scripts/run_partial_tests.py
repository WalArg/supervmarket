import asyncio
import os
import sys

sys.stdout.reconfigure(line_buffering=True)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))

from verify_m3_adversarial_empirical import (
    test_adversarial_intent_and_equipment_queries,
    test_hybrid_search_merging_invariants,
    test_gondola_products_health_and_network
)

async def run_all_except_thread_bench():
    t1 = await test_adversarial_intent_and_equipment_queries()
    t3 = test_hybrid_search_merging_invariants()
    t4 = await test_gondola_products_health_and_network()
    print("\n--- RESULTS OF 1, 3, 4 ---")
    print(f"Task 1 (Intent & 0 accessories in Top 10): {'PASS' if t1 else 'FAIL'}")
    print(f"Task 3 (Hybrid search merging invariants): {'PASS' if t3 else 'FAIL'}")
    print(f"Task 4 (Gondolas health & network liveness): {'PASS' if t4 else 'FAIL'}")

asyncio.run(run_all_except_thread_bench())
