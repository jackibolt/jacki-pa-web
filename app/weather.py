"""Weather for the Today page, from Open-Meteo (free, no key). Location comes from settings:
WEATHER_LAT, WEATHER_LON, WEATHER_PLACE (default Hendersonville, TN). Fails quietly: no weather beats a broken page."""
import os
import time
from datetime import date, datetime

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


def _hours(hourly, now_iso):
    """Every other hour for the next 12 hours (6 slots), plus a one-line heads-up if something matters."""
    times = hourly['time']
    start = next((n for n, t in enumerate(times) if t >= now_iso[:13] + ':00'), None)
    if start is None:
        return [], None
    window = range(start, min(start + 12, len(times)))
    slots = []
    for n in list(window)[::2]:
        emoji, words = _look(hourly['weather_code'][n])
        slots.append({'label': datetime.fromisoformat(times[n]).strftime('%-I %p'), 'emoji': emoji, 'words': words,
                      'temp': round(hourly['temperature_2m'][n]), 'rain': hourly['precipitation_probability'][n] or 0})
    heads_up = None
    wet = next((n for n in window if (hourly['precipitation_probability'][n] or 0) >= 50), None)
    if wet is not None:
        heads_up = f"Rain likely around {datetime.fromisoformat(times[wet]).strftime('%-I %p')}"
    elif any(hourly['temperature_2m'][n] <= 32 for n in window):
        heads_up = 'Freezing temperatures ahead'
    return slots, heads_up


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
            'hourly': 'temperature_2m,precipitation_probability,weather_code',
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
        hours, heads_up = _hours(body['hourly'], cur['time']) if body.get('hourly') else ([], None)
        data = {'place': place, 'days': days, 'hours': hours, 'heads_up': heads_up,
                'now': {'temp': round(cur['temperature_2m']), 'feels': round(cur['apparent_temperature']),
                        'wind': round(cur['wind_speed_10m']), 'emoji': emoji, 'words': words}}
    except Exception as e:
        print(f"Weather unavailable: {type(e).__name__}")
        if hit:
            data = hit[1]  # keep the last good forecast
    _cache[key] = (time.time(), data)
    return data
