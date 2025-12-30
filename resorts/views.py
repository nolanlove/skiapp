"""
Views for the resorts app.
"""
import json
import time
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Resort
from .scraper import get_or_refresh_resorts
from .geocoding import geocode_location
from .distance import filter_resorts_by_distance

logger = logging.getLogger(__name__)


def _format_drive_time(hours: float) -> str:
    """Format drive time as human-readable string."""
    if not hours:
        return None
    total_minutes = int(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    if h == 0:
        return f"{m}min"
    elif m == 0:
        return f"{h}h"
    else:
        return f"{h}h {m}min"


def index(request):
    """Main page with search form and map."""
    return render(request, 'resorts/index.html')


@require_GET
def search_resorts(request):
    """
    API endpoint to search for resorts near a location.
    
    Query params:
        - location: zip code or "City, State"
        - radius: search radius in miles (default 100) - this is DRIVING distance
        - priority: 'snow' or 'distance' - which dimension to prioritize (default 'snow')
    """
    timings = {}
    total_start = time.time()
    
    location = request.GET.get('location', '').strip()
    radius = int(request.GET.get('radius', 100))
    priority = request.GET.get('priority', 'snow')  # 'snow' or 'distance'
    
    if not location:
        return JsonResponse({'error': 'Location is required'}, status=400)
    
    # Geocode the location
    t0 = time.time()
    coords = geocode_location(location)
    timings['geocoding_ms'] = round((time.time() - t0) * 1000)
    
    if not coords:
        return JsonResponse({'error': 'Could not find location. Try a different format.'}, status=400)
    
    user_lat, user_lng = coords
    
    # Get all resorts (from cache or fresh scrape)
    t0 = time.time()
    resorts = get_or_refresh_resorts()
    timings['get_resorts_ms'] = round((time.time() - t0) * 1000)
    timings['total_resorts'] = len(resorts)
    
    # Filter by distance and get nearby resorts with priority-based ranking
    t0 = time.time()
    nearby = filter_resorts_by_distance(resorts, user_lat, user_lng, radius, priority=priority)
    timings['filter_distance_ms'] = round((time.time() - t0) * 1000)
    timings['candidates_after_filter'] = len(nearby)
    
    # Take top 10
    top_resorts = nearby[:10]
    
    # Format response
    t0 = time.time()
    results = []
    for resort_data in top_resorts:
        resort = resort_data['resort']
        driving_hours = resort_data.get('driving_hours')
        results.append({
            'id': resort.id,
            'name': resort.name,
            'state': resort.state,
            'latitude': resort.latitude,
            'longitude': resort.longitude,
            'is_open': resort.is_open,
            'base_depth': resort.base_depth,
            'new_snow_24h': resort.new_snow_24h,
            'trails_open': resort.trails_open,
            'trails_total': resort.trails_total,
            'lifts_open': resort.lifts_open,
            'lifts_total': resort.lifts_total,
            'trails_percent_open': resort.trails_percent_open,
            'conditions_summary': resort.get_conditions_summary(),
            'url': resort.url,
            # Driving distance is now the primary distance metric
            'drive_miles': round(resort_data['distance'], 1),
            'drive_hours': round(driving_hours, 2) if driving_hours else None,
            'drive_time': _format_drive_time(driving_hours) if driving_hours else None,
            # 2D optimization scores
            'snow_quality_score': round(resort_data.get('quality_score', 0) * 100),
            'distance_score': round(resort_data.get('distance_score', 0) * 100),
            'overall_score': round(resort_data.get('combined_score', 0) * 100),
        })
    timings['format_response_ms'] = round((time.time() - t0) * 1000)
    
    timings['total_ms'] = round((time.time() - total_start) * 1000)
    
    # Log timing breakdown
    logger.info(f"Search timings: {timings}")
    
    return JsonResponse({
        'user_location': {
            'latitude': user_lat,
            'longitude': user_lng,
            'query': location,
        },
        'radius': radius,
        'count': len(results),
        'resorts': results,
        'timings': timings,  # Include in response for debugging
    })


@require_GET  
def get_all_resorts(request):
    """API endpoint to get all cached resorts."""
    resorts = get_or_refresh_resorts()
    
    results = [{
        'id': r.id,
        'name': r.name,
        'state': r.state,
        'latitude': r.latitude,
        'longitude': r.longitude,
        'is_open': r.is_open,
    } for r in resorts if r.latitude and r.longitude]
    
    return JsonResponse({'count': len(results), 'resorts': results})

