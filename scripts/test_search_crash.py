import asyncio
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "api"))

from index import app
from httpx import ASGITransport, AsyncClient

async def test_search_meli_without_ean():
    import _lib.mercadolibre as meli
    orig_fetch = meli.fetch_mercadolibre_live

    async def mock_fetch(client, query, limit=10, cp=None, vertical=None):
        return [{
            "nombre": "Smart TV Philco 43 Pulgadas Full HD",
            "marca": "Philco",
            "precio": 350000.0,
            "precio_lista": 400000.0,
            "link": "https://articulo.mercadolibre.com.ar/MLA-99999",
            "ean": "",  # No EAN!
            "modelo": "",  # No modelo!
            "seller_name": "Tienda Philco",
            "imagen": "https://http2.mlstatic.com/test.jpg"
        }]

    meli.fetch_mercadolibre_live = mock_fetch

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            resp = await ac.get("/api/search?q=smart tv&limit=5")
            print("Response status code:", resp.status_code)
            if resp.status_code == 500:
                print("CRASH REPRODUCED: /api/search returns HTTP 500 Internal Server Error!")
            else:
                print("Response json:", resp.json())
        finally:
            meli.fetch_mercadolibre_live = orig_fetch

asyncio.run(test_search_meli_without_ean())
