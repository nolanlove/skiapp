"""
Geocoding service using OpenStreetMap Nominatim API.
"""
import logging
import re
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# User agent as required by Nominatim usage policy
HEADERS = {
    'User-Agent': 'SkiSpotter/1.0 (https://github.com/skispotter)',
    'Accept': 'application/json',
}


def geocode_location(location: str) -> Optional[Tuple[float, float]]:
    """
    Convert a location string (zip code or city, state) to coordinates.
    
    Args:
        location: A zip code (e.g., "80302") or city/state (e.g., "Denver, CO")
    
    Returns:
        Tuple of (latitude, longitude) or None if not found
    """
    if not location:
        return None
    
    location = location.strip()
    
    # Check if it looks like a zip code
    if re.match(r'^\d{5}(-\d{4})?$', location):
        return geocode_zip(location)
    
    # Otherwise treat as city/state
    return geocode_city_state(location)


def geocode_zip(zip_code: str) -> Optional[Tuple[float, float]]:
    """
    Geocode a US zip code.
    """
    params = {
        'postalcode': zip_code[:5],  # Use only 5-digit zip
        'countrycodes': 'us',
        'format': 'json',
        'limit': 1,
    }
    
    return _make_nominatim_request(params)


def geocode_city_state(location: str) -> Optional[Tuple[float, float]]:
    """
    Geocode a city/state combination.
    """
    # Normalize common state abbreviations
    location = normalize_state_abbreviation(location)
    
    params = {
        'q': f"{location}, USA",
        'format': 'json',
        'limit': 1,
    }
    
    return _make_nominatim_request(params)


def normalize_state_abbreviation(location: str) -> str:
    """
    Expand state abbreviations to full names for better geocoding.
    """
    state_map = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
        'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
        'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
        'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
        'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
        'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
        'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
        'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
        'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
        'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
        'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
        'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
    }
    
    # Try to find and replace state abbreviation at the end
    match = re.search(r',\s*([A-Z]{2})$', location.upper())
    if match:
        abbr = match.group(1)
        if abbr in state_map:
            prefix = location[:match.start()]
            return f"{prefix}, {state_map[abbr]}"
    
    return location


def _make_nominatim_request(params: dict) -> Optional[Tuple[float, float]]:
    """
    Make a request to the Nominatim API.
    """
    try:
        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()
        
        results = response.json()
        
        if results and len(results) > 0:
            lat = float(results[0]['lat'])
            lon = float(results[0]['lon'])
            logger.info(f"Geocoded '{params}' to ({lat}, {lon})")
            return lat, lon
        
        logger.warning(f"No results for geocoding: {params}")
        return None
        
    except requests.RequestException as e:
        logger.error(f"Geocoding request failed: {e}")
        return None
    except (KeyError, ValueError, IndexError) as e:
        logger.error(f"Error parsing geocoding response: {e}")
        return None


def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """
    Convert coordinates to a place name (for display purposes).
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    
    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'zoom': 10,  # City level
    }
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        
        if 'display_name' in result:
            # Return a shortened version
            parts = result['display_name'].split(',')
            if len(parts) >= 2:
                return f"{parts[0].strip()}, {parts[1].strip()}"
            return parts[0].strip()
        
        return None
        
    except Exception as e:
        logger.error(f"Reverse geocoding failed: {e}")
        return None

