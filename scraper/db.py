"""Persistencia del scraper (v2 ultra-rápida con executemany y soporte de promociones estructuradas).

Dos backends según DATABASE_URL:
  - sqlite:///...   -> sqlite3 / aiosqlite (desarrollo local, guardado en bloque en <0.1s)
  - postgres://...  -> asyncpg (producción / Neon, guardado en bloque con executemany)
"""
import os
import sqlite3
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_PG = REPO_ROOT / "db" / "schema.sql"

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS productos (
  ean TEXT PRIMARY KEY, nombre TEXT NOT NULL, marca TEXT, modelo TEXT, tipo TEXT,
  imagen TEXT, supermercado_origen TEXT, categorias TEXT, categoria_normalizada TEXT,
  actualizado TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS precios (
  ean TEXT NOT NULL, supermercado TEXT NOT NULL, precio_venta REAL NOT NULL,
  precio_lista REAL, descuento REAL DEFAULT 0,
  promo_etiqueta TEXT, promo_tipo TEXT, promo_min_qty INTEGER DEFAULT 1,
  precio_promo_unit REAL, requiere_club INTEGER DEFAULT 0,
  precio_por_unidad REAL, unidad_medida TEXT, stock INTEGER DEFAULT 0,
  internal_id TEXT, link TEXT, fecha TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (ean, supermercado)
);
CREATE TABLE IF NOT EXISTS historial_precios (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ean TEXT NOT NULL, supermercado TEXT NOT NULL,
  precio_venta REAL NOT NULL, fecha TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_precios_ean ON precios(ean);
CREATE INDEX IF NOT EXISTS idx_precios_super ON precios(supermercado);
"""

SQLITE_MIGRATIONS = [
    "ALTER TABLE precios ADD COLUMN promo_etiqueta TEXT",
    "ALTER TABLE precios ADD COLUMN promo_tipo TEXT",
    "ALTER TABLE precios ADD COLUMN promo_min_qty INTEGER DEFAULT 1",
    "ALTER TABLE precios ADD COLUMN precio_promo_unit REAL",
    "ALTER TABLE precios ADD COLUMN requiere_club INTEGER DEFAULT 0",
]


def _sqlite_path(dsn: str) -> str:
    raw = dsn.split(":///", 1)[1] if ":///" in dsn else "./supervmarket.db"
    if os.path.isabs(raw):
        return raw
    return str(REPO_ROOT / raw.lstrip("./").lstrip(".\\"))


class Database:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get("DATABASE_URL", "sqlite:///./supervmarket.db")
        self.is_sqlite = self.dsn.startswith("sqlite")
        self.sqlite_file = _sqlite_path(self.dsn) if self.is_sqlite else None
        self.conn = None   # sqlite3 directo (evita deadlocks de hilos de aiosqlite en Windows)
        self.pool = None   # asyncpg

    async def connect(self):
        if self.is_sqlite:
            self.conn = sqlite3.connect(self.sqlite_file, timeout=30)
            self.conn.execute("PRAGMA synchronous = NORMAL;")
        else:
            import asyncpg
            self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)

    async def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.pool:
            await self.pool.close()

    async def init_schema(self):
        if self.is_sqlite:
            self.conn.executescript(SCHEMA_SQLITE)
            for stmt in SQLITE_MIGRATIONS:
                try:
                    self.conn.execute(stmt)
                except Exception:
                    pass
            self.conn.commit()
        else:
            sql = SCHEMA_PG.read_text(encoding="utf-8")
            async with self.pool.acquire() as conn:
                await conn.execute(sql)

    async def save_batch(self, products: list[dict]):
        if not products:
            return
        clean = [d for d in products if d.get("ean") and d.get("precio_venta")]
        if not clean:
            return
        if self.is_sqlite:
            self._save_sqlite_fast(clean)
        else:
            await self._save_pg_fast(clean)

    def _save_sqlite_fast(self, products: list[dict]):
        prod_rows = []
        price_rows = []
        hist_rows = []
        for d in products:
            ean = str(d["ean"])
            sup = d.get("supermercado")
            p_venta = float(d["precio_venta"])
            p_promo = float(d.get("precio_promo_unit") or p_venta)
            req_club = 1 if d.get("requiere_club") else 0

            prod_rows.append((
                ean, d.get("nombre"), d.get("marca"), d.get("modelo"),
                d.get("tipo"), d.get("imagen"), sup, d.get("categorias"),
            ))
            price_rows.append((
                ean, sup, p_venta, float(d.get("precio_lista") or p_venta),
                float(d.get("descuento") or 0), d.get("promo_etiqueta"),
                d.get("promo_tipo"), int(d.get("promo_min_qty") or 1),
                p_promo, req_club, d.get("precio_por_unidad"),
                d.get("unidad_medida"), int(d.get("stock") or 0),
                str(d.get("itemId") or ""), d.get("link"),
            ))
            hist_rows.append((ean, sup, p_venta))

        with self.conn:
            self.conn.executemany(
                """INSERT INTO productos
                   (ean,nombre,marca,modelo,tipo,imagen,supermercado_origen,categorias,actualizado)
                   VALUES (?,?,?,?,?,?,?,?,datetime('now'))
                   ON CONFLICT(ean) DO UPDATE SET
                     nombre=excluded.nombre, marca=COALESCE(excluded.marca,productos.marca),
                     imagen=COALESCE(excluded.imagen,productos.imagen),
                     categorias=COALESCE(excluded.categorias,productos.categorias),
                     actualizado=datetime('now')""",
                prod_rows,
            )
            self.conn.executemany(
                """INSERT INTO precios
                   (ean,supermercado,precio_venta,precio_lista,descuento,
                    promo_etiqueta,promo_tipo,promo_min_qty,precio_promo_unit,requiere_club,
                    precio_por_unidad,unidad_medida,stock,internal_id,link,fecha)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
                   ON CONFLICT(ean,supermercado) DO UPDATE SET
                     precio_venta=excluded.precio_venta, precio_lista=excluded.precio_lista,
                     descuento=excluded.descuento, promo_etiqueta=excluded.promo_etiqueta,
                     promo_tipo=excluded.promo_tipo, promo_min_qty=excluded.promo_min_qty,
                     precio_promo_unit=excluded.precio_promo_unit, requiere_club=excluded.requiere_club,
                     precio_por_unidad=excluded.precio_por_unidad,
                     unidad_medida=excluded.unidad_medida, stock=excluded.stock,
                     internal_id=excluded.internal_id, link=excluded.link, fecha=datetime('now')""",
                price_rows,
            )
            self.conn.executemany(
                "INSERT INTO historial_precios (ean,supermercado,precio_venta) VALUES (?,?,?)",
                hist_rows,
            )

    async def _save_pg_fast(self, products: list[dict]):
        prod_rows = []
        price_rows = []
        hist_rows = []
        for d in products:
            ean = str(d["ean"])
            sup = d.get("supermercado")
            p_venta = float(d["precio_venta"])
            p_promo = float(d.get("precio_promo_unit") or p_venta)
            req_club = bool(d.get("requiere_club"))

            prod_rows.append((
                ean, d.get("nombre"), d.get("marca"), d.get("modelo"),
                d.get("tipo"), d.get("imagen"), sup, d.get("categorias"),
            ))
            price_rows.append((
                ean, sup, p_venta, float(d.get("precio_lista") or p_venta),
                float(d.get("descuento") or 0), d.get("promo_etiqueta"),
                d.get("promo_tipo"), int(d.get("promo_min_qty") or 1),
                p_promo, req_club, d.get("precio_por_unidad"),
                d.get("unidad_medida"), int(d.get("stock") or 0),
                str(d.get("itemId") or ""), d.get("link"),
            ))
            hist_rows.append((ean, sup, p_venta))

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    """INSERT INTO productos
                       (ean,nombre,marca,modelo,tipo,imagen,supermercado_origen,categorias,actualizado)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8, now())
                       ON CONFLICT (ean) DO UPDATE SET
                         nombre=EXCLUDED.nombre, marca=COALESCE(EXCLUDED.marca,productos.marca),
                         imagen=COALESCE(EXCLUDED.imagen,productos.imagen),
                         categorias=COALESCE(EXCLUDED.categorias,productos.categorias),
                         actualizado=now()""",
                    prod_rows,
                )
                await conn.executemany(
                    """INSERT INTO precios
                       (ean,supermercado,precio_venta,precio_lista,descuento,
                        promo_etiqueta,promo_tipo,promo_min_qty,precio_promo_unit,requiere_club,
                        precio_por_unidad,unidad_medida,stock,internal_id,link,fecha)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15, now())
                       ON CONFLICT (ean,supermercado) DO UPDATE SET
                         precio_venta=EXCLUDED.precio_venta, precio_lista=EXCLUDED.precio_lista,
                         descuento=EXCLUDED.descuento, promo_etiqueta=EXCLUDED.promo_etiqueta,
                         promo_tipo=EXCLUDED.promo_tipo, promo_min_qty=EXCLUDED.promo_min_qty,
                         precio_promo_unit=EXCLUDED.precio_promo_unit, requiere_club=EXCLUDED.requiere_club,
                         precio_por_unidad=EXCLUDED.precio_por_unidad,
                         unidad_medida=EXCLUDED.unidad_medida, stock=EXCLUDED.stock,
                         internal_id=EXCLUDED.internal_id, link=EXCLUDED.link, fecha=now()""",
                    price_rows,
                )
                await conn.executemany(
                    "INSERT INTO historial_precios (ean,supermercado,precio_venta) VALUES ($1,$2,$3)",
                    hist_rows,
                )
