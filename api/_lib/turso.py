"""api/_lib/turso.py

Cliente HTTP de alto rendimiento para Turso / LibSQL Database en la nube.
Usa el endpoint /v2/pipeline de Turso sobre HTTP/2 con httpx.
Emula `sqlite3.Row` para mantener 100% de compatibilidad con las consultas
existentes de SuperVmarket (FTS5 trigram, índices, .keys() y acceso por nombre de columna).
"""

import os
import re
import httpx
from typing import Any, List, Optional

_DEFAULT_URL = "https://supervmarket-walarg.aws-sa-east-1.turso.io"
_DEFAULT_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTQ3OTcxMzMsImlkIjoiMDFhMWUyM2UtNzkwMS03ZGE2LWJmOGMtMjhlNzY5OGY4ZDkyIiwia2lkIjoiRkNKbFZJM05fdzBFZG51RU1zWmp1eWxZdW5nMVdHT25lWDMzcmNISV9JcyIsInJpZCI6IjIyMzYxMDM5LWJiMDMtNDliNi1hMzFkLTJiYzIyNGU5NzZiZCJ9.qrswQjXyAlAugwuSfbJ4HHeMEyVUnXaew2bpil8S7OzWQ7gmYPnhT_x-ZJKPChLsAaXsLlJVZfS-vnyCjISuDA"

_TURSO_RAW_URL = os.environ.get("TURSO_DATABASE_URL") or os.environ.get("DATABASE_URL") or _DEFAULT_URL
_TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN") or _DEFAULT_TOKEN

# Normalizar URL: libsql:// -> https://
if _TURSO_RAW_URL.startswith("libsql://"):
    TURSO_HTTP_URL = _TURSO_RAW_URL.replace("libsql://", "https://")
elif _TURSO_RAW_URL.startswith("http://") or _TURSO_RAW_URL.startswith("https://"):
    TURSO_HTTP_URL = _TURSO_RAW_URL
else:
    TURSO_HTTP_URL = _DEFAULT_URL

IS_TURSO_CONFIGURED = bool(TURSO_HTTP_URL and _TURSO_TOKEN and "turso.io" in TURSO_HTTP_URL)


class TursoRow(dict):
    """Wrapper que emula sqlite3.Row / asyncpg.Record: acceso tipo dict r['col'] y r.keys()."""
    def __init__(self, cols: list, vals: list):
        super().__init__(zip(cols, vals))
        self._cols = cols

    def keys(self):
        return self._cols


def _to_arg(val: Any) -> dict:
    if val is None:
        return {"type": "null"}
    elif isinstance(val, bool):
        return {"type": "integer", "value": "1" if val else "0"}
    elif isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    elif isinstance(val, float):
        return {"type": "float", "value": val}
    else:
        return {"type": "text", "value": str(val)}


def _from_val(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return raw
    t = raw.get("type")
    v = raw.get("value")
    if t == "null":
        return None
    elif t == "integer":
        return int(v) if v is not None else None
    elif t == "float":
        return float(v) if v is not None else None
    else:
        return v


_client: Optional[httpx.AsyncClient] = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        limits = httpx.Limits(max_connections=50, max_keepalive_connections=20, keepalive_expiry=60.0)
        timeout = httpx.Timeout(connect=5.0, read=12.0, write=10.0, pool=5.0)
        _client = httpx.AsyncClient(limits=limits, timeout=timeout)
    return _client


async def query(sql: str, args: list = None, timeout: float = 12.0) -> List[TursoRow]:
    """Ejecuta una consulta SQL en Turso y retorna lista de TursoRow."""
    if not IS_TURSO_CONFIGURED:
        return []
    args = args or []
    pipeline_url = f"{TURSO_HTTP_URL.rstrip('/')}/v2/pipeline"
    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": [_to_arg(a) for a in args]
                }
            },
            {"type": "close"}
        ]
    }
    headers = {
        "Authorization": f"Bearer {_TURSO_TOKEN}",
        "Content-Type": "application/json"
    }
    client = _get_client()
    resp = await client.post(pipeline_url, json=payload, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        return []
    data = resp.json()
    results = data.get("results", [])
    if not results or results[0].get("type") != "ok":
        return []
    result = results[0]["response"]["result"]
    cols = [c["name"] for c in result.get("cols", [])]
    rows = []
    for r in result.get("rows", []):
        vals = [_from_val(cell) for cell in r]
        rows.append(TursoRow(cols, vals))
    return rows


async def execute(sql: str, args: list = None, timeout: float = 12.0) -> bool:
    """Ejecuta una instrucción SQL de escritura en Turso."""
    if not IS_TURSO_CONFIGURED:
        return False
    args = args or []
    pipeline_url = f"{TURSO_HTTP_URL.rstrip('/')}/v2/pipeline"
    payload = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": [_to_arg(a) for a in args]
                }
            },
            {"type": "close"}
        ]
    }
    headers = {
        "Authorization": f"Bearer {_TURSO_TOKEN}",
        "Content-Type": "application/json"
    }
    client = _get_client()
    resp = await client.post(pipeline_url, json=payload, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        return False
    data = resp.json()
    results = data.get("results", [])
    return bool(results and results[0].get("type") == "ok")
