import requests
from datetime import date, timedelta

def weather_openmeteo(lat, lon):
    today = date.today()
    start = today - timedelta(days=30)

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max"
        f"&start_date={start}&end_date={today + timedelta(days=7)}"
        f"&timezone=auto"
    )
    r = requests.get(url)
    data = r.json()

    if "daily" not in data:
        return f"Error from Open-Meteo API: {data}"

    daily = data["daily"]

    # Get area name using reverse geocoding (OpenStreetMap Nominatim)
    try:
        geo_res = requests.get(
            f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json",
            headers={"User-Agent": "KrishiMitra/1.0"}
        )
        geo_json = geo_res.json()
        area_name = geo_json.get("display_name", None)
    except Exception:
        area_name = None

    # Today's weather (8th from last, as -8)
    today_temp_max = daily["temperature_2m_max"][-8]
    today_temp_min = daily["temperature_2m_min"][-8]
    today_precip = daily["precipitation_sum"][-8]
    today_wind = daily["windspeed_10m_max"][-8]
    today_code = daily["weathercode"][-8]

    # Emoji for today's weather
    def weather_emoji(code):
        # Open-Meteo weather codes: https://open-meteo.com/en/docs#api_form
        if code in [0]:
            return "☀️ Sunny"
        elif code in [1, 2, 3]:
            return "🌤️ Partly Cloudy"
        elif code in [45, 48]:
            return "🌫️ Fog"
        elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
            return "🌦️ Rain"
        elif code in [71, 73, 75, 77, 85, 86]:
            return "❄️ Snow"
        elif code in [95, 96, 99]:
            return "⛈️ Thunderstorm"
        else:
            return "☁️ Cloudy"

    today_emoji = weather_emoji(today_code)

    # Last 30 days rainfall
    last_30_rain = daily["precipitation_sum"][:30]
    last_30_sum = sum(last_30_rain)
    last_10_avg = sum(last_30_rain[-10:]) / 10

    # Forecast summary (next 7 days)
    forecast_lines = []
    for i in range(-7, 0):
        date_str = daily["time"][i]
        tmax = daily["temperature_2m_max"][i]
        tmin = daily["temperature_2m_min"][i]
        rain = daily["precipitation_sum"][i]
        wind = daily["windspeed_10m_max"][i]
        code = daily["weathercode"][i]
        emoji = weather_emoji(code)
        forecast_lines.append(f"{emoji} {date_str}: {tmin}–{tmax}°C, {rain} mm rain, wind {wind} km/h")

    return {
        "today": {
            "temp_min": today_temp_min,
            "temp_max": today_temp_max,
            "precip": today_precip,
            "wind": today_wind,
            "emoji": today_emoji
        },
        "area_name": area_name
    }
