"""Acceso a datos para la API (v2 con soporte de ofertas estructuradas e historial).

Soporta dos backends según DATABASE_URL:
  - postgres://...  -> asyncpg (producción / Vercel + Neon)
  - sqlite:///...   -> sqlite3 directo con función `unaccent` (desarrollo local <2ms, sin deadlocks de hilos)
"""
import os
import sys
import time
import json
import sqlite3
import asyncio
import unicodedata
from .stores import supports_cart
from .parsers import (
    extraer_unidad_titulo,
    normalizar_unidad,
    sanity_precio_unidad,
    NON_GROCERY_MARKETPLACE_KEYWORDS,
    NON_GROCERY_CATEGORY_KEYWORDS,
)
try:
    from .normalization import extract_model
except ImportError:
    from normalization import extract_model

_DSN = os.environ.get("DATABASE_URL", "sqlite:///./supervmarket.db")
IS_SQLITE = _DSN.startswith("sqlite")
_SNAPSHOT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verified_offers_snapshot.json")

SQLITE_MIGRATIONS = [
    "ALTER TABLE precios ADD COLUMN promo_etiqueta TEXT",
    "ALTER TABLE precios ADD COLUMN promo_tipo TEXT",
    "ALTER TABLE precios ADD COLUMN promo_min_qty INTEGER DEFAULT 1",
    "ALTER TABLE precios ADD COLUMN precio_promo_unit REAL",
    "ALTER TABLE precios ADD COLUMN requiere_club INTEGER DEFAULT 0",
    "ALTER TABLE precios ADD COLUMN seller_id TEXT DEFAULT '1'",
    "ALTER TABLE precios ADD COLUMN store_type TEXT DEFAULT 'supermarket'",
    "ALTER TABLE productos ADD COLUMN modelo TEXT",
    "ALTER TABLE productos ADD COLUMN tipo TEXT",
    "CREATE INDEX IF NOT EXISTS idx_precios_seller ON precios (seller_id)",
    "CREATE INDEX IF NOT EXISTS idx_precios_store_type ON precios (store_type)",
    "CREATE INDEX IF NOT EXISTS idx_productos_modelo ON productos (modelo)",
    "CREATE INDEX IF NOT EXISTS idx_productos_tipo ON productos (tipo)",
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
_sqlite_is_memory: bool = False


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
    global _sqlite_conn, _sqlite_is_memory
    if _sqlite_conn is None:
        path = _sqlite_path()
        try:
            if not os.path.exists(path):
                _sqlite_conn = sqlite3.connect(":memory:", check_same_thread=False)
                _sqlite_is_memory = True
            else:
                _sqlite_conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
                _sqlite_is_memory = False
        except Exception:
            _sqlite_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _sqlite_is_memory = True
        _sqlite_conn.row_factory = sqlite3.Row
        _sqlite_conn.create_function("unaccent", 1, _py_unaccent)
        for stmt in SQLITE_MIGRATIONS:
            try:
                _sqlite_conn.execute(stmt)
            except Exception:
                pass
        try:
            _sqlite_conn.execute(
                "CREATE TABLE IF NOT EXISTS verified_deals_cache (cp TEXT PRIMARY KEY, updated_at REAL, payload_json TEXT)"
            )
            # Safe backfill for existing rows
            _sqlite_conn.execute(
                "UPDATE precios SET seller_id = '1' WHERE seller_id IS NULL OR seller_id = ''"
            )
            _sqlite_conn.execute(
                "UPDATE precios SET store_type = 'pharmacy' WHERE supermercado IN ('Farmacity', 'Farmaplus', 'Farmaonline', 'Simplicity', 'Pigmento') AND (store_type IS NULL OR store_type = '' OR store_type = 'supermarket')"
            )
            _sqlite_conn.execute(
                "UPDATE precios SET store_type = 'specialty' WHERE supermercado = 'TheFoodMarket' AND (store_type IS NULL OR store_type = '' OR store_type = 'supermarket')"
            )
            _sqlite_conn.execute(
                "UPDATE precios SET store_type = 'electro' WHERE supermercado IN ('Fravega', 'Cetrogar', 'Naldo', 'Pardo', 'Coppel', 'Samsung', 'Philips', 'Whirlpool', 'Moulinex', 'Sony') AND (store_type IS NULL OR store_type = '' OR store_type = 'supermarket')"
            )
            _sqlite_conn.execute(
                "UPDATE precios SET store_type = 'marketplace' WHERE supermercado IN ('Provincia Compras', 'On City') AND (store_type IS NULL OR store_type = '' OR store_type = 'supermarket')"
            )
            _sqlite_conn.execute(
                "UPDATE precios SET store_type = 'supermarket' WHERE store_type IS NULL OR store_type = ''"
            )
            _sqlite_conn.execute(
                "UPDATE productos SET tipo = 'pharmacy' WHERE (tipo IS NULL OR tipo = '') AND (supermercado_origen IN ('Farmacity', 'Farmaplus', 'Farmaonline', 'Simplicity', 'Pigmento') OR categorias LIKE '%Salud%' OR categorias LIKE '%Belleza%' OR categorias LIKE '%Perfumer%')"
            )
            _sqlite_conn.execute(
                "UPDATE productos SET tipo = 'electro' WHERE (tipo IS NULL OR tipo = '') AND (categorias LIKE '%Electro%' OR categorias LIKE '%Celulares%' OR categorias LIKE '%Informatica%' OR categorias LIKE '%Calefacc%')"
            )
            _sqlite_conn.execute(
                "UPDATE productos SET tipo = 'supermarket' WHERE tipo IS NULL OR tipo = ''"
            )
            rows_tech = _sqlite_conn.execute(
                "SELECT ean, nombre, marca FROM productos WHERE (modelo IS NULL OR modelo = '') AND (tipo = 'electro' OR categorias LIKE '%Electro%' OR categorias LIKE '%Celular%')"
            ).fetchall()
            for row in rows_tech:
                m = extract_model(row["nombre"] or "", row["marca"] or "")
                if m:
                    _sqlite_conn.execute("UPDATE productos SET modelo = ? WHERE ean = ?", (m, row["ean"]))
            _sqlite_conn.commit()
        except Exception:
            pass
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

    seller_id = str(r["seller_id"]) if ("seller_id" in keys and r["seller_id"]) else "1"
    store_type = str(r["store_type"]) if ("store_type" in keys and r["store_type"]) else "supermarket"
    modelo = str(r["modelo"]) if ("modelo" in keys and r["modelo"]) else ""
    tipo = str(r["tipo"]) if ("tipo" in keys and r["tipo"]) else ""

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
        "seller_id": seller_id,
        "store_type": store_type,
        "modelo": modelo,
        "tipo": tipo,
    }


# ---------- API pública ----------
async def search_grouped(
    query: str,
    sort_by: str = "price_asc",
    only_offers: bool = False,
    limit: int = 120,
    vertical: str | None = None,
    store_type: str | None = None,
    grocery_only: bool = False,
) -> list[dict]:
    tokens = [t for t in query.split() if t]
    order_col = (
        "pr.precio_por_unidad"
        if sort_by == "unit_price_asc"
        else "COALESCE(pr.precio_promo_unit, pr.precio_venta)"
    )

    target_verticals = set()
    if vertical and vertical.strip().lower() not in ("todos", "all", ""):
        target_verticals.update(v.strip().lower() for v in vertical.split(",") if v.strip() and v.strip().lower() not in ("todos", "all"))
    if store_type and store_type.strip().lower() not in ("todos", "all", ""):
        target_verticals.update(st.strip().lower() for st in store_type.split(",") if st.strip() and st.strip().lower() not in ("todos", "all"))

    conds = []
    args = []

    if IS_SQLITE:
        search_expr = (
            "unaccent(lower(p.nombre || ' ' || COALESCE(p.marca, '') || ' ' || "
            "p.ean || ' ' || COALESCE(pr.supermercado, '') || ' ' || COALESCE(p.categorias, '')))"
        )
        conds.extend([f"{search_expr} LIKE ?" for _ in tokens])
        args.extend([f"%{_norm(t)}%" for t in tokens])
        if target_verticals:
            ph = ",".join("?" * len(target_verticals))
            conds.append(f"(COALESCE(pr.store_type, 'supermarket') IN ({ph}) OR COALESCE(p.tipo, 'supermarket') IN ({ph}))")
            args.extend(list(target_verticals))
            args.extend(list(target_verticals))
        if grocery_only:
            conds.append("COALESCE(pr.store_type, 'supermarket') NOT IN ('electro', 'marketplace')")
            conds.append("COALESCE(p.tipo, 'supermarket') NOT IN ('electro', 'hogar', 'tecnologia', 'ferreteria')")
            conds.append("(COALESCE(p.categorias, '') NOT LIKE '%Electro%' AND COALESCE(p.categorias, '') NOT LIKE '%Celulares%' AND COALESCE(p.categorias, '') NOT LIKE '%Informatica%')")
    else:
        search_expr = (
            "lower(unaccent(p.nombre || ' ' || COALESCE(p.marca, '') || ' ' || "
            "p.ean || ' ' || COALESCE(pr.supermercado, '') || ' ' || COALESCE(p.categorias, '')))"
        )
        conds.extend([f"{search_expr} LIKE lower(unaccent(${i}))" for i in range(1, len(tokens) + 1)])
        args.extend([f"%{t}%" for t in tokens])
        if target_verticals:
            idx1 = len(args) + 1
            idx2 = len(args) + 2
            conds.append(f"(COALESCE(pr.store_type, 'supermarket') = ANY(${idx1}::text[]) OR COALESCE(p.tipo, 'supermarket') = ANY(${idx2}::text[]))")
            args.append(list(target_verticals))
            args.append(list(target_verticals))
        if grocery_only:
            conds.append("COALESCE(pr.store_type, 'supermarket') NOT IN ('electro', 'marketplace')")
            conds.append("COALESCE(p.tipo, 'supermarket') NOT IN ('electro', 'hogar', 'tecnologia', 'ferreteria')")
            conds.append("(COALESCE(p.categorias, '') NOT ILIKE '%Electro%' AND COALESCE(p.categorias, '') NOT ILIKE '%Celulares%' AND COALESCE(p.categorias, '') NOT ILIKE '%Informatica%')")

    if only_offers:
        conds.append("((pr.promo_etiqueta IS NOT NULL AND pr.requiere_club = 0) OR pr.descuento >= 5)")

    where_clause = " AND ".join(conds) if conds else "1=1"
    safe_limit = max(20, min(int(limit or 120), 300))

    # Si el usuario buscó un término, priorizamos los productos cuyo nombre empieza con la palabra buscada
    # (ej: buscando "leche" aparece "Leche La Serenísima" antes que "Pepitas de dulce de leche").
    if tokens and IS_SQLITE:
        first_tok = _norm(tokens[0]).replace("'", "''")
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
        "p.ean, p.nombre, p.marca, p.modelo, p.tipo, p.categorias, p.imagen, pr.supermercado, pr.precio_venta, "
        "pr.precio_lista, pr.stock, pr.link, pr.internal_id, pr.precio_por_unidad, "
        "pr.unidad_medida, pr.descuento, pr.promo_etiqueta, pr.promo_tipo, "
        "pr.promo_min_qty, pr.precio_promo_unit, pr.requiere_club, pr.seller_id, pr.store_type"
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
        keys = r.keys()
        st_val = r["store_type"] if "store_type" in keys and r["store_type"] else ""
        tp_val = r["tipo"] if "tipo" in keys and r["tipo"] else ""
        if grocery_only:
            cat_val = r["categorias"] if "categorias" in keys and r["categorias"] else ""
            norm_nom = _norm(r["nombre"])
            norm_cat = _norm(cat_val)
            if st_val in ("electro", "marketplace") or tp_val in ("electro", "hogar", "tecnologia", "ferreteria"):
                continue
            if any(kw in norm_nom or kw in norm_cat for kw in NON_GROCERY_MARKETPLACE_KEYWORDS):
                continue
            if any(ck in norm_cat for ck in NON_GROCERY_CATEGORY_KEYWORDS):
                continue
        g = grouped.setdefault(r["ean"], {
            "id": r["ean"],
            "ean": r["ean"],
            "nombre": r["nombre"],
            "marca": r["marca"],
            "modelo": r["modelo"] if "modelo" in keys and r["modelo"] else "",
            "tipo": tp_val,
            "vertical": tp_val or st_val or "supermarket",
            "imagen": r["imagen"],
            "offers": [],
        })
        g["offers"].append(_offer_row(r))

    results = []
    for ean in eans:
        g = grouped.get(ean)
        if not g or not g.get("offers"):
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
        g["best_offer"] = g["offers"][0] if g["offers"] else None
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
        "p.ean, p.nombre, p.marca, p.modelo, p.tipo, pr.supermercado, pr.precio_venta, pr.precio_lista, pr.stock, "
        "pr.link, pr.internal_id, pr.precio_por_unidad, pr.unidad_medida, pr.descuento, "
        "pr.promo_etiqueta, pr.promo_tipo, pr.promo_min_qty, pr.precio_promo_unit, pr.requiere_club, "
        "pr.seller_id, pr.store_type"
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


async def save_verified_deals_snapshot(*args, **kwargs) -> bool:
    """Guarda un snapshot verificado de ofertas en SQLite/Postgres con fallback local en JSON."""
    payload_data = None
    cp_key = "global"

    if "payload" in kwargs:
        payload_data = kwargs["payload"]
    if "cp" in kwargs:
        cp_key = str(kwargs["cp"] or "global").strip() or "global"

    if len(args) == 1:
        if isinstance(args[0], dict) and payload_data is None:
            payload_data = args[0]
        elif isinstance(args[0], str) and "cp" not in kwargs:
            cp_key = args[0].strip() or "global"
    elif len(args) >= 2:
        if isinstance(args[0], dict):
            payload_data = args[0]
            cp_key = str(args[1] or "global").strip() or "global"
        else:
            cp_key = str(args[0] or "global").strip() or "global"
            payload_data = args[1]

    if not isinstance(payload_data, dict):
        return False
    now = time.time()
    saved = False

    try:
        payload_str = json.dumps(payload_data, ensure_ascii=False)
    except Exception:
        return False

    if IS_SQLITE:
        try:
            conn = _get_sqlite()
            conn.execute(
                "CREATE TABLE IF NOT EXISTS verified_deals_cache (cp TEXT PRIMARY KEY, updated_at REAL, payload_json TEXT)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO verified_deals_cache (cp, updated_at, payload_json) VALUES (?, ?, ?)",
                (cp_key, now, payload_str),
            )
            conn.commit()
            saved = True
        except Exception:
            pass
    else:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS verified_deals_cache (cp TEXT PRIMARY KEY, updated_at DOUBLE PRECISION, payload_json TEXT)"
                )
                await conn.execute(
                    "INSERT INTO verified_deals_cache (cp, updated_at, payload_json) VALUES ($1, $2, $3) "
                    "ON CONFLICT (cp) DO UPDATE SET updated_at = EXCLUDED.updated_at, payload_json = EXCLUDED.payload_json",
                    cp_key,
                    now,
                    payload_str,
                )
                saved = True
        except Exception:
            pass

    if (IS_SQLITE and _sqlite_is_memory) or not saved:
        try:
            existing: dict = {}
            if os.path.exists(_SNAPSHOT_FILE):
                with open(_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict) and "tiers" not in loaded:
                        existing = loaded
            existing[cp_key] = {
                "updated_at": now,
                "payload": payload_data,
            }
            with open(_SNAPSHOT_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False)
            saved = True
        except Exception:
            pass

    return saved


async def load_verified_deals_snapshot(cp: str = "global", max_age_seconds: float = 43200.0) -> dict | None:
    """Carga un snapshot verificado de ofertas desde SQLite/Postgres o el fallback local en JSON."""
    cp_key = str(cp or "global").strip() or "global"
    now = time.time()

    if IS_SQLITE:
        try:
            conn = _get_sqlite()
            conn.execute(
                "CREATE TABLE IF NOT EXISTS verified_deals_cache (cp TEXT PRIMARY KEY, updated_at REAL, payload_json TEXT)"
            )
            cur = conn.execute(
                "SELECT updated_at, payload_json FROM verified_deals_cache WHERE cp = ?",
                (cp_key,),
            )
            row = cur.fetchone()
            cur.close()
            if row and row["payload_json"]:
                updated_at = float(row["updated_at"] or 0.0)
                if max_age_seconds <= 0 or (now - updated_at) <= max_age_seconds:
                    data = json.loads(row["payload_json"])
                    if isinstance(data, dict):
                        return data
        except Exception:
            pass
    else:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS verified_deals_cache (cp TEXT PRIMARY KEY, updated_at DOUBLE PRECISION, payload_json TEXT)"
                )
                row = await conn.fetchrow(
                    "SELECT updated_at, payload_json FROM verified_deals_cache WHERE cp = $1",
                    cp_key,
                )
                if row and row["payload_json"]:
                    updated_at = float(row["updated_at"] or 0.0)
                    if max_age_seconds <= 0 or (now - updated_at) <= max_age_seconds:
                        data = json.loads(row["payload_json"])
                        if isinstance(data, dict):
                            return data
        except Exception:
            pass

    try:
        if os.path.exists(_SNAPSHOT_FILE):
            with open(_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                entry = raw.get(cp_key) or (raw.get("global") if cp_key != "global" else None) or (raw if "tiers" in raw else None)
                if isinstance(entry, dict):
                    if "payload" in entry and isinstance(entry["payload"], dict):
                        updated_at = float(entry.get("updated_at") or 0.0)
                        if max_age_seconds <= 0 or (now - updated_at) <= max_age_seconds:
                            return entry["payload"]
                    elif "tiers" in entry:
                        return entry
    except Exception:
        pass

    return None
