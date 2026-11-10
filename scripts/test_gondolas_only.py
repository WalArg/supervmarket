import asyncio
import os
import sys

sys.stdout.reconfigure(line_buffering=True)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts"))

from verify_m3_adversarial_empirical import test_gondola_products_health_and_network

asyncio.run(test_gondola_products_health_and_network())
