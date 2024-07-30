from typing import TypedDict

import requests
from duckduckgo_search import DDGS
from goose3 import Goose

from core.logger import log


class WeatherCoordinatesParams(TypedDict):
    latitude: float
    longitude: float


class WeatherLocationParams(TypedDict):
    location: str


class WebSearchParams(TypedDict):
    keywords: str


class CoordinatesParams(TypedDict):
    location: str


class Tools:

    class AdditionalTools:
        key: str
        function: callable

    def __init__(self, additional_tools: AdditionalTools = {}) -> None:
        self.additional_tools = additional_tools

    def available_tools(self) -> dict:
        return {
            "websearch": self.websearch,
            "get_weather": self.get_weather,
            **self.additional_tools,
        }

    def get_tools_json(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "clear_conversation_history",
                    "description": "Clear the entire conversation history.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "websearch",
                    "description": "Search the internet for the given keywords.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "string",
                                "description": "The keywords or text to search for.",
                            }
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the weather forecast for a location.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The location to get the weather forecast for.",
                            },
                        },
                    },
                },
            },
        ]

    def websearch(self, params: WebSearchParams, max_results=3):
        """
        Search the internet for the given keywords.

        Parameters:
            keywords (str): The keywords or text to search for.
            max_results (int): Maximum number of results to return.

        Returns:
            list: The scraped content with title, URL, and content.
        """
        self.ddgs = DDGS()
        self.goose = Goose()

        log.debug(
            f"Starting web search with params: {params}, max_results: {max_results}"
        )
        results = self.ddgs.text(
            params["keywords"],
            max_results=max_results,
            safesearch="off",
        )
        scraped_content = []

        for result in results:
            try:
                log.debug(f"Checking URL: {result['href']}")
                response = requests.head(result["href"])
                if response.status_code != 200:
                    log.warning(
                        f"Skipping {result['href']} - Received status code: {response.status_code}"
                    )
                    continue

                article = self.goose.extract(url=result["href"])
                scraped_content.append(
                    {
                        "title": article.title,
                        "url": result["href"],
                        "content": article.cleaned_text,
                    }
                )
                log.info(f"Successfully scraped content from: {result['href']}")
            except Exception as e:
                log.error(f"Error scraping {result['href']}: {e}")

        return scraped_content

    def get_weather(self, params: WeatherCoordinatesParams | WeatherLocationParams):
        lat = ""
        lon = ""
        if "latitude" in params and "longitude" in params:
            lat = params["latitude"]
            lon = params["longitude"]
            log.info(f"Using provided coordinates: lat={lat}, lon={lon}")
        else:
            location = params["location"]
            log.info(f"Getting coordinates for location: {location}")
            coordinates = self._get_coordinates({"location": location})
            if "error" in coordinates:
                log.error(
                    f"Failed to get coordinates for {location}: {coordinates['error']}"
                )
                return coordinates
            lat = coordinates["latitude"]
            lon = coordinates["longitude"]
            log.info(f"Coordinates for {location}: lat={lat}, lon={lon}")

        base_url = "https://api.open-meteo.com/v1/dwd-icon"
        hourly_vars = [
            "temperature_2m",
            "precipitation",
        ]
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": ",".join(hourly_vars),
            "timezone": "auto",  # Automatically determine timezone based on location
            "forecast_days": 1,  # Get the forecast for the next day
        }
        log.info(f"Sending request to {base_url} with params {params}")
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            log.info(f"Received successful response: {response.status_code}")
            data = response.json()
            # Clean up the response data
            for key in [
                "latitude",
                "longitude",
                "generationtime_ms",
                "utc_offset_seconds",
                "timezone",
                "timezone_abbreviation",
            ]:
                data.pop(key, None)
            return data
        else:
            log.error(
                f"Failed to get weather data: {response.status_code} - {response.text}"
            )
            return {"error": "Error getting weather data"}

    def _get_coordinates(self, params: CoordinatesParams):
        """
        Search for a location using a free-form query.

        Parameters:
            location (str): The location to search for.
        Returns:
            dict: The location data with latitude and longitude.
        """
        try:
            location = params["location"]
            url = "https://nominatim.openstreetmap.org/search"
            _params = {"q": location, "format": "jsonv2"}
            headers = {
                "accept": "application/json",
                "accept-language": "de-DE,de;q=0.7",
                "cache-control": "max-age=0",
                "if-modified-since": "Tue, 12 Jul 2022 08:34:49 GMT",
                "if-none-match": '"62cd3229-30c"',
                "priority": "u=0, i",
                "sec-ch-ua": '"Not)A;Brand";v="99", "Brave";v="127", "Chromium";v="127"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
                "sec-fetch-user": "?1",
                "sec-gpc": "1",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                "referer": "https://www.google.com",
            }

            log.info(f"Sending request to {url} with params {_params}")
            response = requests.get(
                url, params=_params, allow_redirects=True, headers=headers
            )
            if response.status_code != 200:
                log.error(
                    f"Failed to get coordinates: {response.status_code} - {response.text}"
                )
                raise Exception("Error getting coordinates")

            log.info(
                f"Received successful response for coordinates: {response.status_code}"
            )
            first = response.json()[0]
            return {
                "latitude": float(first["lat"]),
                "longitude": float(first["lon"]),
            }
        except Exception as e:
            log.error(f"Error getting coordinates: {e}")
            return {"error": "Error getting coordinates"}
