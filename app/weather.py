"""Weather for the Today page, from Open-Meteo (free, no key). Location comes from settings:
WEATHER_LAT, WEATHER_LON, WEATHER_PLACE (default Hendersonville, TN). Fails quietly: no weather beats a broken page."""
import os
import time
from datetime import date

import requests

CACHE_SECONDS = 900
_cache = {}

# WMO weather codes -> (emoji, words)
CODES = {0: ('☀️', 'Clear'), 1: ('🌤️', 'Mostly clear'), 2: ('⛅', 'Partly cloudy'), 3: ('☁️', 'Cloudy'),
         45: ('🌫️', 'Fog'), 48: ('🌫️', 'Fog'),
         51: ('🌦️', 'Light drizzle'), 53: ('🌦️', 'Drizzle'), 55: ('🌦️', 'Heavy drizzle'),
         56: ('🌧️', 'Freezing drizzle'), 57: ('🌧️', 'Freezing drizzle'),
         61: ('🌧️', 'Light rain'), 63: ('🌧️', 'Rain'), 65: ('🌧️', 'Heavy rain'),
         66: ('🌧️', 'Freezing rain'), 67: ('🌧️', 'Freezing rain'),
         71: ('🌨️', 'Light snow'), 73: ('🌨️', 'Snow'), 75: ('❄️', 'Heavy snow'), 77: ('🌨️', 'Snow grains'),
         80: ('🌦️', 'Light showers'), 81: ('🌧️', 'Showers'), 82: ('⛈️', 'Heavy showers'),
         85: ('🌨️', 'Snow showers'), 86: ('❄️', 'Heavy snow showers'),
         95: ('⛈️', 'Thunderstorms'), 96: ('⛈️', 'Thunderstorms, hail'), 99: ('⛈️', 'Thunderstorms, hail')}


def _look(code):
    return CODES.get(code, ('🌡️', 'Weather'))


def forecast():
    """{'place', 'now': {...}, 'days': [today + next 3]} or None."""
    lat, lon = os.getenv('WEATHER_LAT', '36.3048'), os.getenv('WEATHER_LON', '-86.6200')
    place = os.getenv('WEATHER_PLACE', 'Hendersonville, TN')
    tz = os.getenv('APP_TIMEZONE', 'America/Chicago')
    key = (lat, lon, tz)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    data = None
    try:
        res = requests.get('https://api.open-meteo.com/v1/forecast', timeout=5, params={
            'latitude': lat, 'longitude': lon, 'timezone': tz, 'forecast_days': 4,
            'temperature_unit': 'fahrenheit', 'wind_speed_unit': 'mph',
            'current': 'temperature_2m,apparent_temperature,weather_code,wind_speed_10m',
            'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max'})
        res.raise_for_status()
        body = res.json()
        cur, daily = body['current'], body['daily']
        emoji, words = _look(cur['weather_code'])
        days = []
        for n, day in enumerate(daily['time']):
            e, w = _look(daily['weather_code'][n])
            days.append({'label': 'Today' if n == 0 else date.fromisoformat(day).strftime('%a'),
                         'emoji': e, 'words': w,
                         'high': round(daily['temperature_2m_max'][n]), 'low': round(daily['temperature_2m_min'][n]),
                         'rain': daily['precipitation_probability_max'][n]})
        data = {'place': place, 'days': days,
                'now': {'temp': round(cur['temperature_2m']), 'feels': round(cur['apparent_temperature']),
                        'wind': round(cur['wind_speed_10m']), 'emoji': emoji, 'words': words}}
    except Exception as e:
        print(f"Weather unavailable: {type(e).__name__}")
        if hit:
            data = hit[1]  # keep the last good forecast
    _cache[key] = (time.time(), data)
    return data
