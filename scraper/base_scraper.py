"""Base de scrapers. Cada scraper descubre URLs y procesa cada producto."""
from abc import ABC, abstractmethod
import asyncio
import aiohttp
from typing import List, Optional, Any

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
}


class BaseScraper(ABC):
    def __init__(self, nombre: str, url_base: str, semaphore_limit: int = 20):
        self.nombre = nombre
        self.url_base = url_base
        self.semaphore_limit = semaphore_limit

    @abstractmethod
    async def obtener_urls(self, session: aiohttp.ClientSession) -> List[Any]:
        ...

    @abstractmethod
    async def procesar(self, session: aiohttp.ClientSession, item: Any,
                       semaforo: asyncio.Semaphore) -> Optional[dict]:
        ...

    async def correr(self, limit: Optional[int] = None) -> List[dict]:
        # Importante: no fijar total=120 a nivel sesión (cortaba corridas largas al minuto 2).
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=12, sock_read=20)
        connector = aiohttp.TCPConnector(limit=self.semaphore_limit * 2, ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            urls = await self.obtener_urls(session)
            if not urls:
                print(f"[{self.nombre}] ⚠️  Sin URLs.")
                return []
            if limit:
                urls = urls[:limit]
            print(f"[{self.nombre}] 🚀 Descargando {len(urls)} productos...")
            semaforo = asyncio.Semaphore(self.semaphore_limit)
            tasks = [self.procesar(session, u, semaforo) for u in urls]
            buffer, done = [], 0
            for fut in asyncio.as_completed(tasks):
                res = await fut
                if res:
                    buffer.append(res)
                done += 1
                if done % 100 == 0:
                    print(f"[{self.nombre}] {done}/{len(urls)}", end="\r")
            print(f"\n[{self.nombre}] ✅ {len(buffer)} productos válidos.")
            return buffer
