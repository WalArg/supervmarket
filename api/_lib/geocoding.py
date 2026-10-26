"""Geocodificación y resolución de ubicación para Argentina.

Permite:
1. Geocodificación inversa (GPS lat/lon -> CP de 4 dígitos + Barrio/Localidad).
2. Búsqueda y autocompletado por nombre de barrio, calle o CP.
3. Diccionario en memoria de zonas populares de CABA, GBA e Interior para respuesta 0ms.
"""
import re
import time
import httpx
from typing import Any

# Cache en memoria: key -> (timestamp, data)
_GEO_CACHE: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 3600 * 24  # 24 horas

# Zonas populares pre-mapeadas (0ms de latencia, 100% offline y sin rate limit)
KNOWN_ZONES: list[dict[str, str]] = [
    # CABA
    {"name": "Palermo", "cp": "1414", "zone": "CABA", "alias": "palermo soho hollywood"},
    {"name": "Caballito", "cp": "1424", "zone": "CABA", "alias": "primera junta parque rivadavia"},
    {"name": "Belgrano", "cp": "1428", "zone": "CABA", "alias": "belgrano r barrancas"},
    {"name": "Recoleta", "cp": "1425", "zone": "CABA", "alias": "barrio norte"},
    {"name": "Almagro", "cp": "1179", "zone": "CABA", "alias": "almagro medrano"},
    {"name": "Villa Urquiza", "cp": "1431", "zone": "CABA", "alias": "urquiza triunvirato"},
    {"name": "Villa Crespo", "cp": "1414", "zone": "CABA", "alias": "crespo warnes"},
    {"name": "Colegiales", "cp": "1426", "zone": "CABA", "alias": "colegiales federico lacroze"},
    {"name": "Núñez", "cp": "1429", "zone": "CABA", "alias": "nunez libertador"},
    {"name": "San Telmo", "cp": "1063", "zone": "CABA", "alias": "san telmo plaza dorrego"},
    {"name": "Flores", "cp": "1406", "zone": "CABA", "alias": "flores rivadavia"},
    {"name": "Balvanera / Once", "cp": "1032", "zone": "CABA", "alias": "once balvanera abasto"},
    {"name": "Barracas", "cp": "1271", "zone": "CABA", "alias": "barracas montes de oca"},
    {"name": "Saavedra", "cp": "1430", "zone": "CABA", "alias": "saavedra dot"},
    {"name": "Devoto", "cp": "1419", "zone": "CABA", "alias": "villa devoto plaza arenales"},
    {"name": "Villa del Parque", "cp": "1417", "zone": "CABA", "alias": "cuenca nazca"},
    {"name": "Chacarita", "cp": "1427", "zone": "CABA", "alias": "chacarita lacroze dorrego"},
    {"name": "Coghlan", "cp": "1430", "zone": "CABA", "alias": "coghlan"},
    {"name": "Boedo", "cp": "1218", "zone": "CABA", "alias": "boedo san juan"},
    {"name": "Parque Patricios", "cp": "1261", "zone": "CABA", "alias": "tecnologico"},
    # GBA Norte
    {"name": "Vicente López", "cp": "1638", "zone": "GBA Norte", "alias": "vte lopez maipu"},
    {"name": "Olivos", "cp": "1636", "zone": "GBA Norte", "alias": "olivos quinta libertador"},
    {"name": "San Isidro", "cp": "1642", "zone": "GBA Norte", "alias": "san isidro centro catedral"},
    {"name": "Martínez", "cp": "1640", "zone": "GBA Norte", "alias": "martinez alvear"},
    {"name": "Acassuso", "cp": "1641", "zone": "GBA Norte", "alias": "acassuso perhuajó"},
    {"name": "San Fernando", "cp": "1646", "zone": "GBA Norte", "alias": "san fernando canal"},
    {"name": "Tigre", "cp": "1648", "zone": "GBA Norte", "alias": "tigre centro estacion delta"},
    {"name": "Nordelta", "cp": "1670", "zone": "GBA Norte", "alias": "nordelta rincon tigre"},
    {"name": "Pilar", "cp": "1629", "zone": "GBA Norte", "alias": "pilar panamericana km 50"},
    # GBA Sur
    {"name": "Avellaneda", "cp": "1870", "zone": "GBA Sur", "alias": "avellaneda mitre"},
    {"name": "Quilmes", "cp": "1878", "zone": "GBA Sur", "alias": "quilmes centro peatonal"},
    {"name": "Bernal", "cp": "1876", "zone": "GBA Sur", "alias": "bernal unq"},
    {"name": "Lanús", "cp": "1824", "zone": "GBA Sur", "alias": "lanus hipolito yrigoyen"},
    {"name": "Banfield", "cp": "1828", "zone": "GBA Sur", "alias": "banfield este oeste"},
    {"name": "Lomas de Zamora", "cp": "1832", "zone": "GBA Sur", "alias": "las lomitas lomas"},
    {"name": "Temperley", "cp": "1834", "zone": "GBA Sur", "alias": "temperley pasco"},
    {"name": "Adrogué", "cp": "1846", "zone": "GBA Sur", "alias": "adrogue almirante brown"},
    # GBA Oeste
    {"name": "Ramos Mejía", "cp": "1704", "zone": "GBA Oeste", "alias": "ramos de mayo avenida"},
    {"name": "Haedo", "cp": "1706", "zone": "GBA Oeste", "alias": "haedo rivadavia"},
    {"name": "Morón", "cp": "1708", "zone": "GBA Oeste", "alias": "moron estacion centro"},
    {"name": "Castelar", "cp": "1712", "zone": "GBA Oeste", "alias": "castelar norte sur"},
    {"name": "Ituzaingó", "cp": "1714", "zone": "GBA Oeste", "alias": "ituzaingo centro"},
    {"name": "San Justo", "cp": "1754", "zone": "GBA Oeste", "alias": "san justo plaza matanza"},
    {"name": "Caseros", "cp": "1678", "zone": "GBA Oeste", "alias": "caseros 3 de febrero"},
    {"name": "San Martín", "cp": "1650", "zone": "GBA Oeste", "alias": "general san martin peatonal"},
    # Interior
    {"name": "La Plata", "cp": "1900", "zone": "Bs. As.", "alias": "la plata plaza moreno"},
    {"name": "Mar del Plata", "cp": "7600", "zone": "Costa", "alias": "mar del plata mdp costa guemes"},
    {"name": "Córdoba Capital", "cp": "5000", "zone": "Córdoba", "alias": "cordoba centro nueva cordoba"},
    {"name": "Rosario", "cp": "2000", "zone": "Santa Fe", "alias": "rosario monumento pichincha centro"},
    {"name": "Mendoza Capital", "cp": "5500", "zone": "Mendoza", "alias": "mendoza peatonal aristides"},
]


def _clean_postal_code(raw: str | None) -> str:
    if not raw:
        return ""
    m = re.search(r"(\d{4})", raw)
    return m.group(1) if m else raw.strip()


async def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    """Resuelve latitud y longitud a CP argentino y Barrio/Localidad."""
    # Redondeo a ~100m para cache inteligente
    cache_key = f"{round(lat, 3)}:{round(lon, 3)}"
    now = time.time()
    if cache_key in _GEO_CACHE:
        ts, data = _GEO_CACHE[cache_key]
        if now - ts < CACHE_TTL:
            return data

    url = "https://nominatim.openstreetmap.org/reverse"
    headers = {"User-Agent": "SuperVmarket/2.0 (soporte@supervmarket.local)"}
    params = {"lat": lat, "lon": lon, "format": "json", "addressdetails": 1}

    async with httpx.AsyncClient(timeout=6.0) as client:
        try:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code == 200:
                data = r.json()
                addr = data.get("address", {})
                raw_cp = addr.get("postcode", "")
                cp = _clean_postal_code(raw_cp)
                
                # Barrio o localidad más representativo
                neighborhood = (
                    addr.get("neighbourhood")
                    or addr.get("suburb")
                    or addr.get("city_district")
                    or addr.get("town")
                    or addr.get("city")
                    or addr.get("municipality")
                    or "Tu ubicación"
                )
                city = addr.get("city") or addr.get("state") or "Argentina"
                
                # Si Nominatim no trajo CP pero tenemos coordenadas, buscamos zona cercana o fallback
                label = f"{neighborhood} ({cp})" if cp else neighborhood

                result = {
                    "ok": True,
                    "cp": cp,
                    "neighborhood": neighborhood,
                    "city": city,
                    "label": label,
                    "display_name": data.get("display_name", ""),
                    "lat": lat,
                    "lon": lon,
                }
                _GEO_CACHE[cache_key] = (now, result)
                return result
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "cp": "",
                "neighborhood": "Ubicación actual",
                "label": "Ubicación actual",
            }

    return {"ok": False, "cp": "", "neighborhood": "Ubicación", "label": "Ubicación"}


async def search_locations(q: str, limit: int = 6) -> list[dict[str, Any]]:
    """Busca barrios, calles o CPs. Combina base instantánea local + Nominatim."""
    clean = q.strip().lower()
    if not clean:
        # Devuelve las zonas más populares por defecto
        return [
            {
                "cp": z["cp"],
                "neighborhood": z["name"],
                "zone": z["zone"],
                "label": f"{z['name']} ({z['cp']})",
                "display_name": f"{z['name']}, {z['zone']}",
            }
            for z in KNOWN_ZONES[:8]
        ]

    # 1. Si es numérico de hasta 4 dígitos (CP directo)
    if clean.isdigit() and len(clean) <= 4:
        # Coincidencia con zonas conocidas
        matches = [
            {
                "cp": z["cp"],
                "neighborhood": z["name"],
                "zone": z["zone"],
                "label": f"{z['name']} ({z['cp']})",
                "display_name": f"{z['name']}, {z['zone']}",
            }
            for z in KNOWN_ZONES
            if z["cp"].startswith(clean)
        ]
        if matches:
            return matches[:limit]
        return [
            {
                "cp": clean,
                "neighborhood": f"CP {clean}",
                "zone": "Argentina",
                "label": f"CP {clean}",
                "display_name": f"Código Postal {clean}",
            }
        ]

    # 2. Búsqueda en zonas pre-mapeadas (match instantáneo)
    local_matches = []
    for z in KNOWN_ZONES:
        full_text = f"{z['name']} {z['zone']} {z.get('alias', '')}".lower()
        if clean in full_text:
            local_matches.append({
                "cp": z["cp"],
                "neighborhood": z["name"],
                "zone": z["zone"],
                "label": f"{z['name']} ({z['cp']})",
                "display_name": f"{z['name']}, {z['zone']}",
            })

    if len(local_matches) >= 3 or len(clean) < 3:
        return local_matches[:limit]

    # 3. Si no alcanzó o es una dirección específica, consultamos Nominatim
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "SuperVmarket/2.0 (soporte@supervmarket.local)"}
    params = {
        "q": q,
        "format": "json",
        "addressdetails": 1,
        "countrycodes": "ar",
        "limit": limit,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code == 200:
                remote_results = []
                for item in r.json():
                    addr = item.get("address", {})
                    raw_cp = addr.get("postcode", "")
                    cp = _clean_postal_code(raw_cp)
                    
                    # Si no vino CP directo en address, podemos intentar inferirlo de lat/lon
                    lat_str = item.get("lat")
                    lon_str = item.get("lon")
                    if not cp and lat_str and lon_str:
                        try:
                            rev = await reverse_geocode(float(lat_str), float(lon_str))
                            cp = rev.get("cp", "")
                        except Exception:
                            pass

                    neighborhood = (
                        addr.get("suburb")
                        or addr.get("neighbourhood")
                        or addr.get("town")
                        or addr.get("city")
                        or addr.get("municipality")
                        or item.get("name")
                    )
                    
                    if cp:
                        remote_results.append({
                            "cp": cp,
                            "neighborhood": neighborhood,
                            "zone": addr.get("state", "Argentina"),
                            "label": f"{neighborhood} ({cp})",
                            "display_name": item.get("display_name", ""),
                            "lat": lat_str,
                            "lon": lon_str,
                        })

                # Combinamos local + remoto sin duplicar CPs
                seen_cps = set()
                combined = []
                for res in local_matches + remote_results:
                    if res["cp"] not in seen_cps:
                        seen_cps.add(res["cp"])
                        combined.append(res)
                return combined[:limit]
    except Exception:
        pass

    return local_matches[:limit]
