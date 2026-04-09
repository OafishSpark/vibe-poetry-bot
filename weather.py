import requests

API_KEY = "031ca61d7c8c3d752b68a9c216271622"  # Replace with your OpenWeatherMap API key
CITY = "498817"
UNITS = "metric"  # Use "imperial" for Fahrenheit, "standard" for Kelvin

def get_weather(city: str, api_key: str, units: str = "metric") -> dict:
    """Fetch current weather data from OpenWeatherMap API."""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "id": city,
        "appid": api_key,
        "units": units,
    }

    response = requests.get(url, params=params)
    response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses
    return response.json()


def display_weather(data: dict, units: str = "metric") -> None:
    """Print a formatted weather summary."""
    temp_unit = "°C" if units == "metric" else ("°F" if units == "imperial" else "K")
    speed_unit = "m/s" if units != "imperial" else "mph"

    # city = data["name"]
    # country = data["sys"]["country"]
    description = data["weather"][0]["description"].capitalize()
    # temp = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    # humidity = data["main"]["humidity"]
    wind_speed = data["wind"]["speed"]
    # visibility = data.get("visibility", "N/A")

    # print(f"\n{'=' * 40}")
    # print(f"  Weather in {city}, {country}")
    # print(f"{'=' * 40}")
    # print(f"  Condition  : {description}")
    # print(f"  Temperature: {temp}{temp_unit} (feels like {feels_like}{temp_unit})")
    # print(f"  Humidity   : {humidity}%")
    # print(f"  Wind Speed : {wind_speed} {speed_unit}")
    # print(f"  Visibility : {visibility} m" if visibility != "N/A" else "  Visibility : N/A")
    # print(f"{'=' * 40}\n")
    weather_report = f'Condition {description}, temperature {feels_like}{temp_unit}, wind {wind_speed} {speed_unit}'
    return weather_report

def get_city_id():
    s_city = "Saint Petersburg"
    city_id = 0
    try:
        res = requests.get("http://api.openweathermap.org/data/2.5/find",
                    params={'q': s_city, 'type': 'like', 'units': 'metric', 'APPID': API_KEY})
        data = res.json()
        cities = ["{} ({})".format(d['name'], d['sys']['country'])
                for d in data['list']]
        print("city:", cities)
        city_id = data['list'][0]['id']
        print('city_id=', city_id)
    except Exception as e:
        print("Exception (find):", e)
        pass

if __name__ == "__main__":
    get_city_id()
    try:
        weather_data = get_weather(CITY, API_KEY, UNITS)
        display_weather(weather_data, UNITS)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e.response.status_code} - {e.response.text}")
    except requests.exceptions.ConnectionError:
        print("Connection error: Check your internet connection.")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")