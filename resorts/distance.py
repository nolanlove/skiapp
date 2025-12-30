"""
Distance calculation utilities including Haversine formula and OSRM routing.
"""
import logging
import math
from typing import List, Dict, Optional, Any

import requests

from .models import Resort

logger = logging.getLogger(__name__)

# OSRM public demo server (for development/testing)
# For production, consider self-hosting or using a paid service
OSRM_URL = "https://router.project-osrm.org"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.
    
    Args:
        lat1, lon1: Latitude and longitude of first point (in degrees)
        lat2, lon2: Latitude and longitude of second point (in degrees)
    
    Returns:
        Distance in miles
    """
    # Earth's radius in miles
    R = 3959
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def filter_resorts_by_distance(
    resorts: List[Resort],
    user_lat: float,
    user_lng: float,
    max_distance: float,
    sort_by: str = 'optimized',
    priority: str = 'snow'
) -> List[Dict[str, Any]]:
    """
    Filter resorts by driving distance from user location and sort them.
    
    Uses a 2D optimization across driving distance and snow quality dimensions.
    The ideal resort is a short drive with great snow.
    
    Args:
        resorts: List of Resort objects
        user_lat, user_lng: User's location
        max_distance: Maximum driving distance in miles
        sort_by: How to sort results ('distance', 'conditions', 'optimized')
        priority: 'snow' or 'distance' - which dimension gets 60% weight
    
    Returns:
        List of dicts with 'resort', driving info, and scores, sorted
    """
    # First pass: use straight-line distance to pre-filter
    # (avoids making OSRM calls for resorts that are clearly too far)
    candidates = []
    
    for resort in resorts:
        if not resort.latitude or not resort.longitude:
            continue
        
        # Use 1.5x max_distance for pre-filter (driving is usually longer than straight-line)
        straight_line = haversine_distance(
            user_lat, user_lng,
            resort.latitude, resort.longitude
        )
        
        if straight_line <= max_distance * 1.5:
            candidates.append(resort)
    
    if not candidates:
        return []
    
    # Second pass: get actual driving distances
    results = []
    for resort in candidates:
        driving_info = get_driving_route(
            user_lat, user_lng,
            resort.latitude, resort.longitude
        )
        
        if driving_info:
            driving_miles = driving_info['distance_miles']
            driving_hours = driving_info['duration_hours']
            
            # Only include if within max driving distance
            if driving_miles <= max_distance:
                snow_quality = _snow_quality_score(resort)
                results.append({
                    'resort': resort,
                    'distance': driving_miles,  # Now this IS driving distance
                    'driving_hours': driving_hours,
                    'snow_quality': snow_quality,
                })
        else:
            # Fallback to straight-line if OSRM fails
            straight_line = haversine_distance(
                user_lat, user_lng,
                resort.latitude, resort.longitude
            )
            if straight_line <= max_distance:
                snow_quality = _snow_quality_score(resort)
                results.append({
                    'resort': resort,
                    'distance': straight_line,
                    'driving_hours': None,  # Unknown
                    'snow_quality': snow_quality,
                })
    
    if not results:
        return results
    
    # Calculate normalized scores for 2D optimization
    max_dist = max(r['distance'] for r in results) or 1
    max_quality = max(r['snow_quality'] for r in results) or 1
    
    for r in results:
        # Normalize distance: 0 = far (bad), 1 = near (good)
        r['distance_score'] = 1 - (r['distance'] / max_dist)
        # Normalize snow quality: 0 = bad, 1 = good (already normalized)
        r['quality_score'] = r['snow_quality'] / max_quality
        # Combined 2D optimization score (higher is better)
        r['combined_score'] = _calculate_2d_score(
            r['distance_score'], 
            r['quality_score'],
            priority=priority
        )
    
    # Sort based on preference
    if sort_by == 'distance':
        results.sort(key=lambda x: x['distance'])
    elif sort_by == 'conditions':
        results.sort(key=lambda x: x['snow_quality'], reverse=True)
    else:  # optimized - 2D optimization across both dimensions
        results.sort(key=lambda x: x['combined_score'], reverse=True)
    
    return results


def _snow_quality_score(resort: Resort) -> float:
    """
    Calculate snow quality score (0-100 scale).
    Higher is better snow conditions.
    
    Factors:
    - Is the resort open? (critical)
    - Base depth (more snow = better)
    - Fresh snow in last 24h (powder days!)
    - Percentage of trails open
    - Percentage of lifts open
    """
    if not resort.is_open:
        return 0.0  # Closed resorts have zero quality
    
    score = 0.0
    
    # Base depth: up to 30 points
    # 60+ inches is excellent, scale linearly
    if resort.base_depth:
        score += min(resort.base_depth / 2, 30)
    
    # Fresh snow is VERY valuable - powder days are gold!
    # Up to 35 points for 14+ inches of new snow
    if resort.new_snow_24h:
        score += min(resort.new_snow_24h * 2.5, 35)
    
    # Trails open percentage: up to 20 points
    if resort.trails_total and resort.trails_open:
        pct = resort.trails_open / resort.trails_total
        score += pct * 20
    
    # Lifts open percentage: up to 15 points
    if resort.lifts_total and resort.lifts_open:
        pct = resort.lifts_open / resort.lifts_total
        score += pct * 15
    
    return score


def _calculate_2d_score(distance_score: float, quality_score: float, priority: str = 'snow') -> float:
    """
    Calculate combined 2D optimization score.
    
    This implements a weighted combination that:
    - Rewards being close (high distance_score)
    - Rewards good snow quality (high quality_score)
    - Uses geometric mean to ensure both dimensions matter
    
    The geometric mean ensures that a resort needs to be decent
    on BOTH dimensions to rank highly - you can't compensate
    for terrible snow with being super close, or vice versa.
    
    Args:
        distance_score: 0-1 where 1 is closest
        quality_score: 0-1 where 1 is best quality
        priority: 'snow' gives 60% weight to snow, 'distance' gives 60% to distance
    
    Returns:
        Combined score (0-1) where higher is better
    """
    # Add small epsilon to avoid zero in geometric mean
    eps = 0.01
    d = distance_score + eps
    q = quality_score + eps
    
    # Weighted geometric mean - priority gets 60%, other gets 40%
    if priority == 'distance':
        quality_weight = 0.4
        distance_weight = 0.6
    else:  # default to snow priority
        quality_weight = 0.6
        distance_weight = 0.4
    
    # Weighted geometric mean formula
    score = (q ** quality_weight) * (d ** distance_weight)
    
    return score


def get_driving_distances(
    user_lat: float,
    user_lng: float,
    resort_list: List[Dict[str, Any]],
    max_resorts: int = 10
) -> List[Dict[str, Any]]:
    """
    Add driving distance and duration to resort list using OSRM.
    
    Args:
        user_lat, user_lng: User's location
        resort_list: List of dicts with 'resort' and 'distance' keys
        max_resorts: Maximum number to calculate driving for (to avoid API abuse)
    
    Returns:
        Updated list with 'driving_distance' and 'driving_duration' added
    """
    # Only calculate for a limited number to respect OSRM usage
    resorts_to_calculate = resort_list[:max_resorts]
    
    for resort_data in resorts_to_calculate:
        resort = resort_data['resort']
        
        driving_info = get_driving_route(
            user_lat, user_lng,
            resort.latitude, resort.longitude
        )
        
        if driving_info:
            resort_data['driving_distance'] = driving_info['distance_miles']
            resort_data['driving_duration'] = driving_info['duration_hours']
        else:
            resort_data['driving_distance'] = None
            resort_data['driving_duration'] = None
    
    return resort_list


def get_driving_route(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float
) -> Optional[Dict[str, float]]:
    """
    Get driving route from OSRM.
    
    Returns:
        Dict with 'distance_miles' and 'duration_hours', or None on error
    """
    # OSRM expects coordinates as lng,lat
    url = f"{OSRM_URL}/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}"
    
    params = {
        'overview': 'false',  # We don't need the route geometry
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('code') == 'Ok' and data.get('routes'):
            route = data['routes'][0]
            
            # Convert meters to miles
            distance_miles = route['distance'] / 1609.344
            
            # Convert seconds to hours
            duration_hours = route['duration'] / 3600
            
            return {
                'distance_miles': round(distance_miles, 1),
                'duration_hours': round(duration_hours, 2),
            }
        
        logger.warning(f"OSRM returned no route: {data.get('code')}")
        return None
        
    except requests.RequestException as e:
        logger.error(f"OSRM request failed: {e}")
        return None
    except (KeyError, ValueError, IndexError) as e:
        logger.error(f"Error parsing OSRM response: {e}")
        return None


def format_duration(hours: float) -> str:
    """
    Format a duration in hours to a human-readable string.
    """
    if hours < 1:
        minutes = round(hours * 60)
        return f"{minutes} min"
    elif hours < 24:
        h = int(hours)
        m = round((hours - h) * 60)
        if m == 0:
            return f"{h} hr"
        return f"{h} hr {m} min"
    else:
        days = int(hours / 24)
        remaining = hours % 24
        h = int(remaining)
        return f"{days} day{'s' if days > 1 else ''} {h} hr"

