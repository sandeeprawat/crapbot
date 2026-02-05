"""Find and test a free weather API."""
import requests
import json

print("=== Finding Free Weather APIs ===\n")

# Option 1: Open-Meteo (No API key needed!)
print("1. Open-Meteo API (https://open-meteo.com/)")
print("   - No API key required")
print("   - Free for non-commercial use")
print("   - Global coverage")

# Test Open-Meteo for Seattle
print("\n   Testing for Seattle, WA...")
try:
    # Get coordinates for Seattle
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_params = {"name": "Seattle", "count": 1, "language": "en", "format": "json"}
    geo_response = requests.get(geocoding_url, params=geo_params, timeout=10)
    
    if geo_response.status_code == 200:
        geo_data = geo_response.json()
        if geo_data.get("results"):
            lat = geo_data["results"][0]["latitude"]
            lon = geo_data["results"][0]["longitude"]
            print(f"   Coordinates: {lat}, {lon}")
            
            # Get weather
            weather_url = "https://api.open-meteo.com/v1/forecast"
            weather_params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "America/Los_Angeles"
            }
            
            weather_response = requests.get(weather_url, params=weather_params, timeout=10)
            if weather_response.status_code == 200:
                weather_data = weather_response.json()
                current = weather_data.get("current", {})
                
                print(f"\n   ✓ Current Weather in Seattle:")
                print(f"     Temperature: {current.get('temperature_2m')}°F")
                print(f"     Humidity: {current.get('relative_humidity_2m')}%")
                print(f"     Wind Speed: {current.get('wind_speed_10m')} mph")
                print(f"     Precipitation: {current.get('precipitation')} mm")
                print(f"     Time: {current.get('time')}")
                print(f"\n   API Response Sample:")
                print(f"   {json.dumps(weather_data, indent=2)[:500]}...")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Option 2: WeatherAPI.com (Free tier available)
print("\n\n2. WeatherAPI.com (https://www.weatherapi.com/)")
print("   - Free tier: 1M calls/month")
print("   - Requires API key (free signup)")
print("   - Real-time, forecast, historical data")

# Option 3: OpenWeatherMap
print("\n3. OpenWeatherMap (https://openweathermap.org/)")
print("   - Free tier: 60 calls/minute, 1M/month")
print("   - Requires API key (free signup)")
print("   - Very popular and widely documented")

# Option 4: NOAA (US Government)
print("\n4. NOAA Weather API (https://www.weather.gov/documentation/services-web-api)")
print("   - Completely free, no API key needed")
print("   - US locations only")
print("   - Government-operated (reliable)")

print("\n\n=== Recommendation ===")
print("For immediate use without signup: Open-Meteo (as tested above)")
print("For production use: OpenWeatherMap or WeatherAPI.com (both have generous free tiers)")

print("\n=== Example Code ===")
print("""
# Using Open-Meteo (no API key)
import requests

def get_weather(city_name):
    # Geocoding
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    geo_response = requests.get(geo_url, params={"name": city_name, "count": 1})
    geo_data = geo_response.json()
    
    if geo_data.get("results"):
        lat = geo_data["results"][0]["latitude"]
        lon = geo_data["results"][0]["longitude"]
        
        # Weather
        weather_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "temperature_unit": "fahrenheit"
        }
        response = requests.get(weather_url, params=params)
        return response.json()

# Usage
weather = get_weather("New York")
print(f"Temperature: {weather['current']['temperature_2m']}°F")
""")
