from flask import Flask, request, jsonify
import requests
from datetime import datetime
import pytz

# Create an instance of the Flask application
app = Flask(__name__)

# Weather code mapping for Open-Meteo
WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

def get_vienna_weather():
    """
    Fetches current weather data for Vienna from the Open-Meteo API.
    Uses the 'forecast' endpoint to retrieve current temperature and weather code.
    Includes robust error handling for API requests.
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast" # Using 'forecast' as it often covers 'current' data reliably
        params = {
            "latitude": 48.2082,
            "longitude": 16.3738,
            "current": "temperature_2m,weather_code", # Requesting specific current variables
            "timezone": "Europe/Vienna", # Specify timezone for current data accuracy
            "forecast_days": 1 # Requesting only the current day's data
        }

        # Make the API request with a timeout
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

        data = response.json()
        current = data.get("current", {})

        temperature = current.get("temperature_2m")
        weather_code = current.get("weather_code")

        # Convert weather_code to integer, default to 0 if None
        weather_code_int = int(weather_code) if weather_code is not None else 0

        return {
            "temperature": f"{temperature}°C" if temperature is not None else "N/A",
            "weather": WEATHER_CODE_MAP.get(weather_code_int, "Unknown"),
            "weather_simple": get_simple_weather(weather_code_int)
        }
    except requests.exceptions.RequestException as e:
        # Catch errors specifically related to the requests library (network, HTTP errors, timeouts)
        print(f"Error fetching weather data (requests error): {e}")
        return {
            "temperature": "N/A",
            "weather": "Unknown",
            "weather_simple": "Unknown"
        }
    except Exception as e:
        # Catch any other unexpected errors during data processing
        print(f"An unexpected error occurred in get_vienna_weather: {e}")
        return {
            "temperature": "N/A",
            "weather": "Unknown",
            "weather_simple": "Unknown"
        }

def get_simple_weather(weather_code):
    """
    Maps Open-Meteo weather codes to simple, display-friendly categories.
    These categories can be used for conditional display (e.g., showing icons).
    """
    if weather_code in [0, 1]:
        return "Sunny"
    elif weather_code in [2, 3, 45, 48]:
        return "Cloudy"
    elif weather_code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
        return "Rainy"
    elif weather_code in [71, 73, 75, 77, 85, 86]:
        return "Snowy"
    elif weather_code in [95, 96, 99]:
        return "Thunderstorm"
    else:
        return "Other"

def get_vienna_time():
    """
    Gets the current local time in Vienna timezone.
    Uses pytz for accurate timezone handling.
    """
    try:
        vienna_tz = pytz.timezone('Europe/Vienna')
        vienna_time = datetime.now(vienna_tz)
        return vienna_time.strftime("%I:%M %p") # Format as HH:MM AM/PM
    except Exception as e:
        print(f"Error getting Vienna time: {e}")
        return "N/A"

@app.route('/')
def hello_world():
    """
    Returns a simple 'Hello, World!' message.
    This is the default endpoint for the Flask application.
    """
    return 'Hello, World!'

@app.route('/trml_webhook', methods=['POST'])
def trml_webhook():
    """
    Handles incoming webhook data from TRML.
    It expects JSON data and prints it to the console for demonstration.
    In a real application, you would process this data and potentially store it
    or use it to update your application's state.
    """
    if request.is_json:
        data = request.get_json()
        print(f"Received TRML webhook data: {data}")

        return jsonify({"status": "success", "message": "Webhook received"}), 200
    else:
        print("Received non-JSON TRML webhook request.")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

@app.route('/trml_data', methods=['GET'])
def trml_data():
    """
    Provides dynamic data for TRML to poll.
    This endpoint fetches current weather data for Vienna and local time.
    """
    weather_data = get_vienna_weather()
    current_time = get_vienna_time()

    data_for_trml = {
        "title": "Vienna Weather Plugin",
        "message": f"Current time in Vienna: {current_time}",
        "temperature": weather_data["temperature"],
        "weather": weather_data["weather_simple"] # Use the simplified weather string for Liquid
    }

    return jsonify(data_for_trml), 200

if __name__ == '__main__':
    # Run the Flask application in debug mode for development.
    # In production, use a production-ready WSGI server like Gunicorn or uWSGI.
    app.run(debug=True)