"""Acceso a datos para la API (v2 con soporte de ofertas estructuradas e historial).

Soporta dos backends según DATABASE_URL:
  - postgres://...  -> asyncpg (producción / Vercel + Neon)
  - sqlite:///...   -> sqlite3 directo con función `unaccent` (desarrollo local <2ms, sin deadlocks de hilos)
"""
import os
import sys
import sqlite3
import asyncio
import unicodedata
from .stores import supports_cart

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRAPER_DIR = os.path.join(REPO_ROOT, "scraper")
if SCRAPER_DIR not in sys.path:
    sys.path.insert(0, SCRAPER_DIR)
from utils import extraer_unidad_titulo, normalizar_unidad, sanity_precio_unidad  # noqa: E402

_DSN = os.environ.get("DATABASE_URL", "sqlite:///./supervmarket.db")
IS_SQLITE = _DSN.startswith("sqlite")

SQLITE_MIGRATIONS = [
    "ALTER TABLE precios ADD COLUMN promo_etiqueta TEXT",
    "ALTER TABLE precios ADD COLUMN promo_tipo TEXT",
    "ALTER TABLE precios ADD COLUMN promo_min_qty INTEGER DEFAULT 1",
    "ALTER TABLE precios ADD COLUMN precio_promo_unit REAL",
    "ALTER TABLE precios ADD COLUMN requiere_club INTEGER DEFAULT 0",
]


def _py_unaccent(text: str) -> str:
    if text is None:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", str(text))
                   if unicodedata.category(c) != "Mn")


def _norm(text: str) -> str:
    return _py_unaccent(text).lower()


def _sqlite_path() -> str:
    raw = _DSN.split(":///", 1)[1] if ":///" in _DSN else "./supervmarket.db"
    if os.path.isabs(raw):
        return raw
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, raw.lstrip("./").lstrip(".\\"))


# ---------- Conexiones ----------
_pg_pool = None
_pg_loop = None
_sqlite_conn: sqlite3.Connection | None = None


async def get_pool():
    global _pg_pool, _pg_loop
    curr_loop = asyncio.get_running_loop()
    if _pg_pool is None or _pg_loop is not curr_loop:
        import asyncpg
        _pg_pool = await asyncpg.create_pool(_DSN, min_size=0, max_size=5,
                                             statement_cache_size=0)
        _pg_loop = curr_loop
    return _pg_pool


def _get_sqlite() -> sqlite3.Connection:
    global _sqlite_conn
    if _sqlite_conn is None:
        _sqlite_conn = sqlite3.connect(_sqlite_path(), check_same_thread=False, timeout=30)
        _sqlite_conn.row_factory = sqlite3.Row
        _sqlite_conn.create_function("unaccent", 1, _py_unaccent)
        for stmt in SQLITE_MIGRATIONS:
            try:
                _sqlite_conn.execute(stmt)
            except Exception:
                pass
        _sqlite_conn.commit()
    return _sqlite_conn


async def _fetch(sql_sqlite: str, sql_pg: str, args: list):
    if IS_SQLITE:
        conn = _get_sqlite()
        cur = conn.execute(sql_sqlite, args)
        rows = cur.fetchall()
        cur.close()
        return rows
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(sql_pg, *args)


# ---------- Helpers ----------
def _offer_row(r) -> dict:
    keys = r.keys()
    precio = float(r["precio_venta"])
    raw_lista = float(r["precio_lista"] or precio)
    if raw_lista > precio * 4.0 or raw_lista < precio:
        precio_lista = precio
        descuento = 0.0
    else:
        precio_lista = raw_lista
        descuento = float(r["descuento"] or 0.0)

    promo_unit = float(r["precio_promo_unit"] if ("precio_promo_unit" in keys and r["precio_promo_unit"]) else precio)
    promo_min_qty = int(r["promo_min_qty"] if ("promo_min_qty" in keys and r["promo_min_qty"]) else 1)
    promo_etiqueta = r["promo_etiqueta"] if "promo_etiqueta" in keys else None
    promo_tipo = r["promo_tipo"] if "promo_tipo" in keys else None
    req_club = bool(r["requiere_club"]) if "requiere_club" in keys else False

    # Calcular el precio por unidad (kg / l / un) sobre el precio efectivo con promo (promo_unit),
    # no sobre el precio sin descuento.
    raw_unit_price = r["precio_por_unidad"]
    if raw_unit_price and precio > 0 and promo_unit < precio:
        eff_unit_price = round(float(raw_unit_price) * (promo_unit / precio), 2)
    else:
        eff_unit_price = float(raw_unit_price) if raw_unit_price else None

    return {
        "supermercado": r["supermercado"],
        "precio": precio,
        "precio_lista": precio_lista,
        "stock": (r["stock"] or 0) > 0,
        "link": r["link"],
        "sku_id": r["internal_id"],
        "unit_price": eff_unit_price,
        "unit_measure": r["unidad_medida"],
        "discount": descuento,
        "promo_label": promo_etiqueta,
        "promo_type": promo_tipo,
        "promo_min_qty": promo_min_qty,
        "promo_unit_price": promo_unit,
        "requires_club": req_club,
        "supports_cart": supports_cart(r["supermercado"]),
    }


# ---------- API pública ----------
async def search_grouped(query: str, sort_by: str = "price_asc", only_offers: bool = False,
                         limit: int = 120) -> list[dict]:
    tokens = [t for t in query.split() if t]
    order_col = (
        "pr.precio_por_unidad"
        if sort_by == "unit_price_asc"
        else "COALESCE(pr.precio_promo_unit, pr.precio_venta)"
    )

    if IS_SQLITE:
        search_expr = (
            "unaccent(lower(p.nombre || ' ' || COALESCE(p.marca, '') || ' ' || "
            "p.ean || ' ' || COALESCE(pr.supermercado, '') || ' ' || COALESCE(p.categorias, '')))"
        )
        conds = [f"{search_expr} LIKE ?" for _ in tokens]
        args = [f"%{_norm(t)}%" for t in tokens]
    else:
        search_expr = (
            "lower(unaccent(p.nombre || ' ' || COALESCE(p.marca, '') || ' ' || "
            "p.ean || ' ' || COALESCE(pr.supermercado, '') || ' ' || COALESCE(p.categorias, '')))"
        )
        conds = [f"{search_expr} LIKE lower(unaccent(${i}))" for i in range(1, len(tokens) + 1)]
        args = [f"%{t}%" for t in tokens]

    if only_offers:
        conds.append("(pr.promo_etiqueta IS NOT NULL OR pr.descuento >= 5)")

    where_clause = " AND ".join(conds) if conds else "1=1"
    safe_limit = max(20, min(int(limit or 120), 300))

    # Si el usuario buscó un término, priorizamos los productos cuyo nombre empieza con la palabra buscada
    # (ej: buscando "leche" aparece "Leche La Serenísima" antes que "Pepitas de dulce de leche").
    if tokens and IS_SQLITE:
        first_tok = _norm(tokens[0])
        starts_expr = (
            f"MAX(CASE WHEN unaccent(lower(p.nombre)) LIKE '{first_tok}%' THEN 2 "
            f"WHEN unaccent(lower(p.nombre)) LIKE '% {first_tok}%' THEN 1 ELSE 0 END)"
        )
    else:
        starts_expr = "1"

    ean_sql = (
        f"SELECT p.ean, MIN({order_col}) AS best, COUNT(DISTINCT pr.supermercado) AS stores_cnt, "
        f"MAX(CASE WHEN pr.promo_etiqueta IS NOT NULL THEN 1 ELSE 0 END) AS has_promo, "
        f"{starts_expr} AS name_rel "
        f"FROM productos p "
        f"JOIN precios pr ON pr.ean = p.ean "
        f"WHERE {where_clause} AND pr.stock > 0 AND {order_col} IS NOT NULL "
        f"GROUP BY p.ean ORDER BY name_rel DESC, stores_cnt DESC, has_promo DESC, best ASC LIMIT {safe_limit}"
    )
    ean_rows = await _fetch(ean_sql, ean_sql, args)
    eans = [r["ean"] for r in ean_rows]
    if not eans:
        return []

    cols = (
        "p.ean, p.nombre, p.marca, p.imagen, pr.supermercado, pr.precio_venta, "
        "pr.precio_lista, pr.stock, pr.link, pr.internal_id, pr.precio_por_unidad, "
        "pr.unidad_medida, pr.descuento, pr.promo_etiqueta, pr.promo_tipo, "
        "pr.promo_min_qty, pr.precio_promo_unit, pr.requiere_club"
    )
    if IS_SQLITE:
        ph = ",".join("?" * len(eans))
        sql = (f"SELECT {cols} FROM productos p JOIN precios pr ON pr.ean = p.ean "
               f"WHERE p.ean IN ({ph}) AND pr.stock > 0")
        rows = await _fetch(sql, sql, eans)
    else:
        sql = (f"SELECT {cols} FROM productos p JOIN precios pr ON pr.ean = p.ean "
               f"WHERE p.ean = ANY($1::text[]) AND pr.stock > 0")
        rows = await _fetch(sql, sql, [eans])

    grouped: dict[str, dict] = {}
    for r in rows:
        g = grouped.setdefault(r["ean"], {
            "ean": r["ean"],
            "nombre": r["nombre"],
            "marca": r["marca"],
            "imagen": r["imagen"],
            "offers": [],
        })
        g["offers"].append(_offer_row(r))

    results = []
    for ean in eans:
        g = grouped.get(ean)
        if not g:
            continue
        # Unificar la cantidad/unidad del grupo por EAN (ej: Multipack 3x90 G = 0.27 kg)
        # y recalcular el precio por kg/litro sobre el precio efectivo con promo de cada tienda.
        cant, u_tit = extraer_unidad_titulo(g["nombre"])
        for o in g["offers"]:
            eff_p = float(o.get("promo_unit_price") or o["precio"])
            if cant > 0:
                p_u, u_norm = normalizar_unidad(eff_p / cant, u_tit)
                o["unit_price"] = sanity_precio_unidad(eff_p, p_u, u_norm)
                o["unit_measure"] = u_norm
        if sort_by == "unit_price_asc":
            g["offers"].sort(key=lambda o: (o["unit_price"] is None, o["unit_price"] or 0))
        else:
            g["offers"].sort(key=lambda o: o.get("promo_unit_price") or o["precio"])
        results.append(g)
    return results


async def suggest(query: str, limit: int = 8) -> list[str]:
    if len(query) < 2:
        return []
    if IS_SQLITE:
        sql = ("SELECT DISTINCT nombre FROM productos WHERE unaccent(lower(nombre)) LIKE ? "
               "ORDER BY length(nombre) ASC LIMIT ?")
        rows = await _fetch(sql, sql, [f"%{_norm(query)}%", limit])
    else:
        sql = ("SELECT DISTINCT nombre FROM productos WHERE lower(unaccent(nombre)) LIKE lower(unaccent($1)) "
               "ORDER BY similarity(lower(unaccent(nombre)), lower(unaccent($2))) DESC LIMIT $3")
        rows = await _fetch(sql, sql, [f"%{query}%", query, limit])
    return [r["nombre"] for r in rows]


async def offers_for_eans(eans: list[str]):
    """Devuelve ({ean: [ofertas...]}, {ean: nombre}) para el optimizador."""
    if not eans:
        return {}, {}
    cols = (
        "p.ean, p.nombre, pr.supermercado, pr.precio_venta, pr.precio_lista, pr.stock, "
        "pr.link, pr.internal_id, pr.precio_por_unidad, pr.unidad_medida, pr.descuento, "
        "pr.promo_etiqueta, pr.promo_tipo, pr.promo_min_qty, pr.precio_promo_unit, pr.requiere_club"
    )
    if IS_SQLITE:
        ph = ",".join("?" * len(eans))
        sql = (f"SELECT {cols} FROM productos p JOIN precios pr ON pr.ean = p.ean "
               f"WHERE p.ean IN ({ph}) AND pr.stock > 0")
        rows = await _fetch(sql, sql, eans)
    else:
        sql = (f"SELECT {cols} FROM productos p JOIN precios pr ON pr.ean = p.ean "
               f"WHERE p.ean = ANY($1::text[]) AND pr.stock > 0")
        rows = await _fetch(sql, sql, [eans])

    out: dict[str, list[dict]] = {}
    names: dict[str, str] = {}
    for r in rows:
        names[r["ean"]] = r["nombre"]
        o = _offer_row(r)
        o["nombre"] = r["nombre"]
        o["ean"] = r["ean"]
        out.setdefault(r["ean"], []).append(o)
    return out, names


async def stats_summary() -> dict:
    """Estadísticas rápidas de catálogo y ofertas activas para mostrar en la portada."""
    sql_prod = "SELECT COUNT(*) AS c FROM productos"
    sql_off = "SELECT COUNT(*) AS c FROM precios WHERE stock > 0"
    sql_promos = "SELECT COUNT(*) AS c FROM precios WHERE stock > 0 AND (promo_etiqueta IS NOT NULL OR descuento >= 5)"
    sql_stores = "SELECT supermercado, COUNT(*) AS c FROM precios WHERE stock > 0 GROUP BY supermercado ORDER BY c DESC"
    r_p = await _fetch(sql_prod, sql_prod, [])
    r_o = await _fetch(sql_off, sql_off, [])
    r_pr = await _fetch(sql_promos, sql_promos, [])
    r_st = await _fetch(sql_stores, sql_stores, [])
    return {
        "productos": r_p[0]["c"] if r_p else 0,
        "ofertas_totales": r_o[0]["c"] if r_o else 0,
        "promociones_activas": r_pr[0]["c"] if r_pr else 0,
        "tiendas": [{"supermercado": r["supermercado"], "productos": r["c"]} for r in r_st],
    }
