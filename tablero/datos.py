"""Consumo y limpieza de datos de la API pública Open-Meteo (Historical Weather API)."""
import time
from datetime import date, timedelta

import pandas as pd
import requests

API_URL = "https://archive-api.open-meteo.com/v1/archive"
API_DOCS = "https://open-meteo.com/en/docs/historical-weather-api"

VARIABLES = [
    "precipitation_sum",           # mm/día
    "temperature_2m_mean",         # °C
    "temperature_2m_min",          # °C
    "temperature_2m_max",          # °C
    "et0_fao_evapotranspiration",  # mm/día (evapotranspiración de referencia FAO-56)
]

# Zonas agrícolas representativas, de norte a sur (coordenadas de la ciudad cabecera).
ZONAS = {
    "copiapo":    {"nombre": "Copiapó",     "region": "Atacama",       "rubro": "uva de mesa",          "lat": -27.37, "lon": -70.33},
    "ovalle":     {"nombre": "Ovalle",      "region": "Coquimbo",      "rubro": "uva pisquera y cítricos", "lat": -30.60, "lon": -71.20},
    "quillota":   {"nombre": "Quillota",    "region": "Valparaíso",    "rubro": "paltos",               "lat": -32.88, "lon": -71.25},
    "rancagua":   {"nombre": "Rancagua",    "region": "O'Higgins",     "rubro": "frutales de exportación", "lat": -34.17, "lon": -70.74},
    "talca":      {"nombre": "Talca",       "region": "Maule",         "rubro": "viñas y berries",      "lat": -35.43, "lon": -71.66},
    "chillan":    {"nombre": "Chillán",     "region": "Ñuble",         "rubro": "cultivos anuales",     "lat": -36.61, "lon": -72.10},
    "losangeles": {"nombre": "Los Ángeles", "region": "Biobío",        "rubro": "cereales y remolacha", "lat": -37.47, "lon": -72.35},
    "temuco":     {"nombre": "Temuco",      "region": "La Araucanía",  "rubro": "trigo y avena",        "lat": -38.74, "lon": -72.60},
    "osorno":     {"nombre": "Osorno",      "region": "Los Lagos",     "rubro": "praderas y lechería",  "lat": -40.57, "lon": -73.13},
}
ZONA_POR_DEFECTO = "talca"
ANIOS_HISTORIA = 10          # años previos usados como referencia
RETRASO_DIAS = 7             # ERA5 se publica con ~5 días de retraso
TIMEOUT_S = 20
TTL_CACHE_S = 3 * 3600       # respeta los límites de consulta de la API

_cache = {}


class ErrorAPI(Exception):
    """La API no respondió o respondió algo inutilizable."""


def ultima_fecha_disponible(hoy=None):
    hoy = hoy or date.today()
    return hoy - timedelta(days=RETRASO_DIAS)


def anios_disponibles(hoy=None):
    ultimo = ultima_fecha_disponible(hoy).year
    return list(range(ultimo, 2015, -1))   # de más reciente a 2016


def _consultar(params):
    """GET a la API con caché en memoria y manejo de errores."""
    clave = tuple(sorted(params.items()))
    guardado = _cache.get(clave)
    if guardado and time.time() - guardado[0] < TTL_CACHE_S:
        return guardado[1]
    try:
        r = requests.get(API_URL, params=params, timeout=TIMEOUT_S)
        r.raise_for_status()
        js = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise ErrorAPI(f"No fue posible consultar Open-Meteo ({exc.__class__.__name__}).") from exc
    if isinstance(js, dict) and js.get("error"):
        raise ErrorAPI(f"Open-Meteo respondió con error: {js.get('reason', 'sin detalle')}")
    _cache[clave] = (time.time(), js)
    return js


def url_consulta(params):
    """URL pública reproducible para que un tercero verifique el dato."""
    return requests.Request("GET", API_URL, params=params).prepare().url


def _params(lats, lons, inicio, fin):
    return {
        "latitude": ",".join(f"{x:.2f}" for x in lats),
        "longitude": ",".join(f"{x:.2f}" for x in lons),
        "start_date": inicio.isoformat(),
        "end_date": fin.isoformat(),
        "daily": ",".join(VARIABLES),
        "timezone": "America/Santiago",
    }


def limpiar(bloque_daily):
    """Convierte el bloque 'daily' de la respuesta en un DataFrame limpio."""
    df = pd.DataFrame(bloque_daily)
    if "time" not in df or df.empty:
        raise ErrorAPI("La respuesta de Open-Meteo no trae datos diarios.")
    df["fecha"] = pd.to_datetime(df.pop("time"))
    df = df.rename(columns={
        "precipitation_sum": "precip",
        "temperature_2m_mean": "tmed",
        "temperature_2m_min": "tmin",
        "temperature_2m_max": "tmax",
        "et0_fao_evapotranspiration": "et0",
    })
    for c in ["precip", "tmed", "tmin", "tmax", "et0"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # 1) Días finales aún no publicados llegan como null: se eliminan.
    df = df.dropna(subset=["precip", "tmed", "tmin", "tmax", "et0"], how="all")
    # 2) Valores físicamente imposibles se descartan (precipitación o ET0 negativas).
    df.loc[df["precip"] < 0, "precip"] = pd.NA
    df.loc[df["et0"] < 0, "et0"] = pd.NA
    # 3) Huecos aislados: precipitación faltante no se inventa (queda NaN y no suma);
    #    temperaturas se interpolan solo si el hueco es de 1-2 días.
    for c in ["tmed", "tmin", "tmax"]:
        df[c] = df[c].interpolate(limit=2)
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month
    df["dia_anio"] = df["fecha"].dt.dayofyear
    df["balance"] = df["precip"] - df["et0"]   # balance hídrico climático diario
    return df.sort_values("fecha").reset_index(drop=True)


def serie_zona(zona_id, anio, hoy=None):
    """Datos diarios de una zona desde (anio - 10) hasta fin de anio (o última fecha disponible)."""
    z = ZONAS[zona_id]
    fin = min(date(anio, 12, 31), ultima_fecha_disponible(hoy))
    inicio = date(anio - ANIOS_HISTORIA, 1, 1)
    params = _params([z["lat"]], [z["lon"]], inicio, fin)
    js = _consultar(params)
    if isinstance(js, list):
        js = js[0]
    return limpiar(js.get("daily", {})), url_consulta(params)


def serie_todas_las_zonas(anio, hoy=None):
    """Datos diarios del año seleccionado para todas las zonas (una sola consulta multi-ubicación)."""
    ids = list(ZONAS)
    fin = min(date(anio, 12, 31), ultima_fecha_disponible(hoy))
    params = _params([ZONAS[i]["lat"] for i in ids], [ZONAS[i]["lon"] for i in ids], date(anio, 1, 1), fin)
    js = _consultar(params)
    if isinstance(js, dict):   # una sola ubicación devuelve objeto, varias devuelven lista
        js = [js]
    if len(js) != len(ids):
        raise ErrorAPI("Open-Meteo devolvió un número inesperado de ubicaciones.")
    marcos = []
    for zid, bloque in zip(ids, js):
        df = limpiar(bloque.get("daily", {}))
        df["zona"] = zid
        marcos.append(df)
    return pd.concat(marcos, ignore_index=True), url_consulta(params)
