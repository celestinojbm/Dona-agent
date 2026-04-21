# agent/real_world.py — Integración de Dona con datos del mundo real
# Dona

"""
Conecta a Dona con APIs externas:
  - Clima:   OpenWeatherMap (OPENWEATHER_API_KEY) — 1,000 llamadas/día gratis
  - Noticias: NewsAPI (NEWS_API_KEY) — 100 llamadas/día gratis
  - Tráfico: Google Maps Distance Matrix (GOOGLE_MAPS_API_KEY) — $200 crédito/mes

Si una API key no está configurada, esa función retorna None silenciosamente.
"""

import os
import hashlib
import logging
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("dona")

OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

TIMEOUT = 10.0

# Descripciones de clima en español legibles
_ICONOS_CLIMA = {
    "clear": "☀️ despejado",
    "clouds": "☁️ nublado",
    "rain": "🌧️ lluvia",
    "drizzle": "🌦️ llovizna",
    "thunderstorm": "⛈️ tormenta",
    "snow": "❄️ nieve",
    "mist": "🌫️ neblina",
    "fog": "🌫️ niebla",
}


# ─── CLIMA ────────────────────────────────────────────────────────────────────

async def obtener_clima(ciudad: str) -> list[dict] | None:
    """
    Retorna el pronóstico por hora para las próximas 12 horas.
    Cada elemento: {hora, temp, descripcion, llueve, main}
    Retorna None si no está configurada la key o falla la API.
    """
    if not OPENWEATHER_KEY or not ciudad:
        return None
    try:
        url = "http://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": ciudad,
            "appid": OPENWEATHER_KEY,
            "units": "metric",
            "lang": "es",
            "cnt": 4,   # 4 intervalos de 3h = 12h
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        pronosticos = []
        for item in data.get("list", []):
            main_str = item["weather"][0]["main"].lower()
            pronosticos.append({
                "hora": item["dt_txt"],
                "temp": round(item["main"]["temp"]),
                "descripcion": item["weather"][0]["description"].capitalize(),
                "icono": _ICONOS_CLIMA.get(main_str, "🌤️"),
                "llueve": main_str in ("rain", "drizzle", "thunderstorm"),
                "main": main_str,
            })
        return pronosticos or None

    except Exception as e:
        logger.debug(f"real_world.obtener_clima ({ciudad}): {e}")
        return None


async def hay_lluvia_en_horas(ciudad: str, hora_utc: datetime) -> bool:
    """
    Retorna True si hay lluvia/tormenta pronosticada dentro de ±2h de hora_utc.
    Útil para cruzar con eventos del calendario.
    """
    pronostico = await obtener_clima(ciudad)
    if not pronostico:
        return False
    for p in pronostico:
        try:
            t = datetime.strptime(p["hora"], "%Y-%m-%d %H:%M:%S")
            diff_h = abs((t - hora_utc).total_seconds() / 3600)
            if diff_h <= 2 and p["llueve"]:
                return True
        except Exception:
            continue
    return False


def resumen_clima_str(pronostico: list[dict]) -> str:
    """Convierte el pronóstico en una frase legible para el morning brief."""
    if not pronostico:
        return ""
    p = pronostico[0]
    lluvia_hoy = any(x["llueve"] for x in pronostico)
    frase = f"{p['icono']} {p['descripcion']}, {p['temp']}°C"
    if lluvia_hoy:
        frase += " — hay lluvia prevista en algún momento del día ☔"
    return frase


# ─── NOTICIAS ─────────────────────────────────────────────────────────────────

async def obtener_noticias(industria: str, pais: str = "México") -> list[dict]:
    """
    Retorna hasta 3 artículos recientes sobre la industria del usuario.
    Cada elemento: {titulo, resumen, url, url_hash}
    Retorna lista vacía si no hay key o falla.
    """
    if not NEWS_API_KEY or not industria:
        return []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": f"{industria} {pais}",
            "sortBy": "publishedAt",
            "language": "es",
            "pageSize": 3,
            "apiKey": NEWS_API_KEY,
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            articles = r.json().get("articles", [])

        resultado = []
        for a in articles:
            art_url = a.get("url", "")
            resultado.append({
                "titulo": a.get("title", ""),
                "resumen": a.get("description", ""),
                "url": art_url,
                "url_hash": hashlib.md5(art_url.encode()).hexdigest()[:16],
            })
        return resultado

    except Exception as e:
        logger.debug(f"real_world.obtener_noticias ({industria}): {e}")
        return []


async def extraer_industria(contexto: str) -> str | None:
    """
    Usa Claude para extraer la industria/sector del usuario desde su contexto de onboarding.
    Retorna una palabra o frase corta (ej: "logística", "tecnología", "construcción").
    """
    if not contexto or len(contexto) < 50:
        return None
    try:
        from agent.llm import completar_texto
        prompt = (
            f"Del siguiente texto, extrae en 1-3 palabras la industria o sector "
            f"principal de trabajo de la persona. Solo la industria, sin explicación.\n\n"
            f"Texto: {contexto[:400]}\n\nIndustria:"
        )
        resultado = await completar_texto(prompt, max_tokens=20)
        industria = resultado.strip().lower() if resultado else None
        return industria if industria and len(industria) < 40 else None
    except Exception as e:
        logger.debug(f"real_world.extraer_industria: {e}")
        return None


# ─── TRÁFICO ─────────────────────────────────────────────────────────────────

async def calcular_trafico(origen: str, destino: str) -> dict | None:
    """
    Calcula el tiempo de viaje con tráfico en tiempo real.
    Retorna: {normal_min, trafico_min, delay_min}
    Requiere GOOGLE_MAPS_API_KEY.
    """
    if not MAPS_API_KEY or not origen or not destino:
        return None
    try:
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            "origins": origen,
            "destinations": destino,
            "departure_time": "now",
            "key": MAPS_API_KEY,
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()

        elemento = data["rows"][0]["elements"][0]
        if elemento.get("status") != "OK":
            return None

        normal_seg = elemento["duration"]["value"]
        trafico_seg = elemento.get("duration_in_traffic", elemento["duration"])["value"]

        return {
            "normal_min": round(normal_seg / 60),
            "trafico_min": round(trafico_seg / 60),
            "delay_min": round((trafico_seg - normal_seg) / 60),
        }
    except Exception as e:
        logger.debug(f"real_world.calcular_trafico: {e}")
        return None
