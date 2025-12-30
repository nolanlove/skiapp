"""
Web scraper for OnTheSnow ski resort data.
"""
import re
import json
import logging
from datetime import timedelta
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.utils import timezone
from django.conf import settings

from .models import Resort

logger = logging.getLogger(__name__)

BASE_URL = "https://www.onthesnow.com"
REGIONS_URL = f"{BASE_URL}/united-states/skireport.html"

# User agent to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# Resort coordinates - many need to be looked up since OTS doesn't always provide them
# This is a fallback for major resorts
RESORT_COORDS = {
    'vail': (39.6403, -106.3742),
    'breckenridge': (39.4817, -106.0384),
    'park-city': (40.6514, -111.5080),
    'mammoth-mountain': (37.6308, -119.0326),
    'jackson-hole': (43.5875, -110.8279),
    'big-sky': (45.2618, -111.4015),
    'aspen-snowmass': (39.2084, -106.9490),
    'steamboat': (40.4572, -106.8045),
    'telluride': (37.9375, -107.8123),
    'taos': (36.5969, -105.4544),
    'squaw-valley-alpine-meadows': (39.1969, -120.2358),
    'heavenly': (38.9353, -119.9400),
    'kirkwood': (38.6850, -120.0653),
    'northstar': (39.2747, -120.1210),
    'sugar-bowl': (39.3047, -120.3344),
    'mt-bachelor': (43.9792, -121.6886),
    'crystal-mountain-washington': (46.9282, -121.5045),
    'stevens-pass': (47.7448, -121.0890),
    'sun-valley': (43.6806, -114.4083),
    'alta': (40.5884, -111.6386),
    'snowbird': (40.5830, -111.6538),
    'deer-valley': (40.6375, -111.4783),
    'brighton': (40.5980, -111.5832),
    'killington': (43.6045, -72.8201),
    'stowe': (44.5303, -72.7814),
    'sugarbush': (44.1357, -72.9012),
    'jay-peak': (44.9275, -72.5050),
    'sunday-river': (44.4736, -70.8567),
    'sugarloaf': (45.0314, -70.3131),
    'loon-mountain': (44.0364, -71.6214),
    'cannon-mountain': (44.1567, -71.6986),
    'okemo': (43.4017, -72.7170),
    'stratton': (43.1136, -72.9081),
    'mount-snow': (42.9601, -72.9204),
    'whiteface': (44.3656, -73.9026),
    'gore-mountain': (43.6717, -74.0067),
    'hunter-mountain': (42.2036, -74.2312),
    'camelback': (41.0519, -75.3567),
    'blue-mountain-pennsylvania': (40.8231, -75.5156),
    'snowshoe': (38.4125, -79.9942),
    'wintergreen': (37.9367, -78.9481),
    'winterplace': (37.5978, -81.1153),
    'boyne-mountain': (45.1628, -84.9364),
    'crystal-mountain-michigan': (44.5250, -85.9986),
    'nubs-nob': (45.4697, -84.9236),
    'big-bear': (34.2358, -116.8906),
    'snow-summit': (34.2311, -116.8917),
    'mountain-high': (34.3717, -117.6908),
    'arapahoe-basin': (39.6425, -105.8719),
    'keystone': (39.6064, -105.9519),
    'copper-mountain': (39.5022, -106.1497),
    'winter-park': (39.8841, -105.7628),
    'loveland': (39.6800, -105.8978),
    'eldora': (39.9375, -105.5828),
    'crested-butte': (38.8986, -106.9650),
    'wolf-creek': (37.4728, -106.7936),
    'purgatory': (37.6303, -107.8142),
    'monarch-mountain': (38.5125, -106.3322),
    'ski-santa-fe': (35.7953, -105.8036),
    'angel-fire': (36.3939, -105.2847),
    'red-river': (36.7064, -105.4072),
    'sipapu': (36.0947, -105.5031),
    'ski-apache': (33.3989, -105.7928),
    'snowbasin': (41.2158, -111.8569),
    'powder-mountain': (41.3789, -111.7811),
    'brian-head': (37.7025, -112.8497),
    'sundance': (40.3925, -111.5878),
    'whitefish-mountain': (48.4836, -114.3553),
    'red-lodge': (45.1853, -109.3417),
    'bridger-bowl': (45.8175, -110.8978),
    'grand-targhee': (43.7903, -110.9581),
    'schweitzer': (48.3675, -116.6222),
    'silver-mountain': (47.5383, -116.1128),
    'lookout-pass': (47.4544, -115.7072),
    'bogus-basin': (43.7647, -116.1028),
    'brundage': (45.0422, -116.1531),
    'timberline-lodge': (45.3306, -121.7108),
    'mt-hood-meadows': (45.3311, -121.6656),
    'mt-hood-skibowl': (45.3033, -121.7578),
    'mt-ashland': (42.0828, -122.7178),
    'anthony-lakes': (44.9617, -118.2306),
    'mission-ridge': (47.2931, -120.4017),
    'snoqualmie-pass': (47.4206, -121.4153),
    'mt-baker': (48.8617, -121.6650),
    'white-pass': (46.6375, -121.3900),
    '49-degrees-north': (48.3014, -117.5617),
    'diamond-peak': (39.2531, -119.9206),
    'mt-rose': (39.3147, -119.8856),
    'sierra-at-tahoe': (38.8000, -120.0800),
    'boreal': (39.3322, -120.3478),
    'soda-springs': (39.3197, -120.3800),
    'donner-ski-ranch': (39.3183, -120.3306),
    'homewood': (39.0856, -120.1608),
    'alpine-meadows': (39.1644, -120.2386),
    'palisades-tahoe': (39.1969, -120.2358),
    'dodge-ridge': (38.1889, -119.9556),
    'bear-valley': (38.4681, -120.0417),
    'june-mountain': (37.7675, -119.0903),
    'china-peak': (37.2347, -119.1572),
    'snow-valley': (34.2247, -117.0356),
    'mount-baldy': (34.2383, -117.6458),
    # New Hampshire
    'attitash': (44.0828, -71.2297),
    'black-mountain': (44.0575, -71.1511),
    'bretton-woods': (44.2586, -71.4392),
    'cranmore-mountain-resort': (44.0542, -71.1086),
    'crotched-mountain': (43.0222, -71.8742),
    'dartmouth-skiway': (43.7856, -72.0869),
    'gunstock': (43.5453, -71.3636),
    'king-pine': (43.8583, -71.1522),
    'mount-sunapee': (43.3256, -72.0817),
    'pats-peak': (43.0761, -71.7828),
    'ragged-mountain-resort': (43.4756, -71.8539),
    'tenney-mountain': (43.8086, -71.7511),
    'waterville-valley': (43.9506, -71.5281),
    'whaleback-mountain': (43.6083, -72.1233),
    'wildcat-mountain': (44.2633, -71.2392),
    # Vermont
    'bolton-valley': (44.4178, -72.8486),
    'bromley-mountain': (43.2178, -72.9397),
    'burke-mountain': (44.5767, -71.8978),
    'killington-resort': (43.6045, -72.8201),
    'mad-river-glen': (44.2039, -72.9192),
    'magic-mountain': (43.1908, -72.7839),
    'okemo-mountain-resort': (43.4017, -72.7170),
    'pico-mountain': (43.6614, -72.8439),
    'saskadena-six': (43.8806, -72.5356),
    'smugglers-notch-resort': (44.5917, -72.7858),
    'stowe-mountain': (44.5303, -72.7814),
    'stratton-mountain': (43.1136, -72.9081),
    # Maine
    'big-moose-mountain': (45.3619, -69.5411),
    'black-mountain-of-maine': (44.4597, -70.7411),
    'camden-snow-bowl': (44.2172, -69.1019),
    'lost-valley': (44.1211, -70.2292),
    'mt-abram-ski-resort': (44.3886, -70.4367),
    'new-hermon-mountain': (44.8556, -68.9272),
    'pleasant-mountain': (44.0533, -70.8758),
    'saddleback-inc': (44.9406, -70.5011),
    # Massachusetts
    'berkshire-east': (42.6272, -72.7583),
    'blue-hills-ski-area': (42.2147, -71.1128),
    'bousquet-ski-area': (42.4128, -73.2356),
    'bradford-ski-area': (42.7600, -71.0856),
    'jiminy-peak': (42.5469, -73.2706),
    'nashoba-valley': (42.5217, -71.4486),
    'otis-ridge-ski-area': (42.1861, -73.0997),
    'ski-butternut': (42.1858, -73.2978),
    'ski-ward': (42.2647, -71.7631),
    'wachusett-mountain-ski-area': (42.5036, -71.8869),
    # Connecticut
    'mohawk-mountain': (41.8367, -73.3150),
    'ski-sundown': (41.9286, -72.9472),
    # New York (additional)
    'belleayre': (42.1306, -74.5083),
    'bristol-mountain': (42.7328, -77.4139),
    'greek-peak': (42.5022, -76.1517),
    'holiday-valley': (42.2592, -78.6722),
    'windham-mountain': (42.2958, -74.2567),
}


def get_or_refresh_resorts():
    """
    Get resorts from database, refreshing if cache is stale.
    """
    cache_timeout = getattr(settings, 'RESORT_CACHE_TIMEOUT', 1800)  # 30 min default
    cache_cutoff = timezone.now() - timedelta(seconds=cache_timeout)
    
    # Check if we have recent data
    recent_count = Resort.objects.filter(last_scraped__gte=cache_cutoff).count()
    
    if recent_count > 50:  # We have enough recent data
        return list(Resort.objects.all())
    
    # Need to refresh
    logger.info("Refreshing resort data from OnTheSnow...")
    try:
        scrape_all_resorts()
    except Exception as e:
        logger.error(f"Error scraping resorts: {e}")
        # Return whatever we have cached
    
    return list(Resort.objects.all())


def scrape_all_resorts():
    """
    Scrape all US ski resorts from OnTheSnow.
    """
    # Get list of states/regions
    states = get_us_states()
    
    for state_name, state_url in states:
        try:
            scrape_state_resorts(state_name, state_url)
        except Exception as e:
            logger.error(f"Error scraping {state_name}: {e}")
            continue


def get_us_states():
    """
    Get list of US states with ski resorts.
    Returns list of (state_name, url) tuples.
    """
    states = [
        ('Colorado', '/colorado/skireport.html'),
        ('California', '/california/skireport.html'),
        ('Utah', '/utah/skireport.html'),
        ('Vermont', '/vermont/skireport.html'),
        ('Montana', '/montana/skireport.html'),
        ('Wyoming', '/wyoming/skireport.html'),
        ('New Mexico', '/new-mexico/skireport.html'),
        ('Idaho', '/idaho/skireport.html'),
        ('Oregon', '/oregon/skireport.html'),
        ('Washington', '/washington/skireport.html'),
        ('New Hampshire', '/new-hampshire/skireport.html'),
        ('Maine', '/maine/skireport.html'),
        ('New York', '/new-york/skireport.html'),
        ('Michigan', '/michigan/skireport.html'),
        ('Wisconsin', '/wisconsin/skireport.html'),
        ('Minnesota', '/minnesota/skireport.html'),
        ('Pennsylvania', '/pennsylvania/skireport.html'),
        ('West Virginia', '/west-virginia/skireport.html'),
        ('Virginia', '/virginia/skireport.html'),
        ('North Carolina', '/north-carolina/skireport.html'),
        ('Massachusetts', '/massachusetts/skireport.html'),
        ('Connecticut', '/connecticut/skireport.html'),
        ('Nevada', '/nevada/skireport.html'),
        ('Arizona', '/arizona/skireport.html'),
        ('Alaska', '/alaska/skireport.html'),
        ('South Dakota', '/south-dakota/skireport.html'),
    ]
    return states


def scrape_state_resorts(state_name: str, state_url: str):
    """
    Scrape all resorts for a given state.
    """
    url = urljoin(BASE_URL, state_url)
    logger.info(f"Scraping {state_name} from {url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return
    
    soup = BeautifulSoup(response.text, 'lxml')
    
    # OnTheSnow now uses a table-based layout
    # Find all table rows (data rows, not headers)
    table_rows = soup.select('table tbody tr')
    if not table_rows:
        table_rows = soup.select('table tr')
    
    # Filter to only rows with td cells (skip header rows)
    data_rows = [row for row in table_rows if row.find('td')]
    
    if data_rows:
        logger.info(f"Found {len(data_rows)} resort rows in table for {state_name}")
        for row in data_rows:
            try:
                parse_table_row(row, state_name)
            except Exception as e:
                logger.error(f"Error parsing table row: {e}")
        return
    
    # Fallback: Try div-based selectors (older layout)
    resort_rows = soup.select('div[data-testid="resort-row"]')
    if not resort_rows:
        resort_rows = soup.select('.styles_row__resort__')
        
    if resort_rows:
        for row in resort_rows:
            try:
                parse_resort_row(row, state_name)
            except Exception as e:
                logger.error(f"Error parsing resort row: {e}")
        return
    
    # Last resort: Try finding links to individual resort pages
    resort_links = soup.select('a[href*="/snow-report.html"]')
    for link in resort_links:
        resort_url = link.get('href', '')
        if resort_url and '/snow-report.html' in resort_url:
            try:
                scrape_individual_resort(resort_url, state_name)
            except Exception as e:
                logger.error(f"Error scraping resort {resort_url}: {e}")


def scrape_individual_resort(resort_url: str, state_name: str):
    """
    Scrape an individual resort's snow report page.
    """
    url = urljoin(BASE_URL, resort_url)
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return
    
    soup = BeautifulSoup(response.text, 'lxml')
    
    # Extract resort name from title or header
    title = soup.find('h1')
    if not title:
        return
    
    name = title.get_text(strip=True)
    name = re.sub(r'\s*Snow Report.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*Ski Resort.*', '', name, flags=re.IGNORECASE)
    
    # Generate slug
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    
    # Try to find coordinates in page scripts
    lat, lng = extract_coordinates_from_page(soup, slug)
    
    # Extract conditions
    conditions = extract_conditions(soup)
    
    # Update or create resort
    Resort.objects.update_or_create(
        slug=slug,
        defaults={
            'name': name,
            'state': state_name,
            'latitude': lat,
            'longitude': lng,
            'url': url,
            **conditions
        }
    )


def parse_trails_lifts_text(text: str) -> tuple:
    """
    Parse trails/lifts text from OnTheSnow's concatenated format.
    
    The format is tricky: "9/1476% Open" means 9/147 trails open (6%)
    The percentage is concatenated directly after the total count.
    
    Examples:
    - "9/1476% Open" -> (9, 147)  # 6% open
    - "45/16516% Open" -> (45, 165)  # ~27% open (website shows 16%)
    - "144/144100% Open" -> (144, 144)  # 100% open
    - "5/9-" -> (5, 9)  # Simple format for lifts
    
    Returns (open_count, total_count) tuple.
    """
    if not text or text == '-':
        return None, None
    
    # Look for pattern: open/combined% 
    match = re.match(r'^(\d+)/(\d+)%', text)
    if match:
        open_count = int(match.group(1))
        combined = match.group(2)
        
        candidates = []
        
        # Try different splits: total_digits + percentage_digits
        for pct_len in [3, 2, 1]:
            if len(combined) > pct_len:
                try:
                    total_count = int(combined[:-pct_len])
                    pct = int(combined[-pct_len:])
                    
                    # Valid percentage must be 0-100
                    if 0 <= pct <= 100 and total_count > 0:
                        # Total must be >= open
                        if total_count >= open_count:
                            calculated_pct = round(open_count / total_count * 100)
                            diff = abs(calculated_pct - pct)
                            
                            # Prefer realistic trail counts (most resorts have < 400 trails)
                            # But don't completely exclude large ones
                            realism_penalty = 0
                            if total_count > 1000:
                                realism_penalty = 500  
                            elif total_count > 500:
                                realism_penalty = 100  
                            
                            # Score: lower is better
                            score = diff + realism_penalty
                            candidates.append((total_count, pct, calculated_pct, diff, pct_len, score))
                except:
                    continue
        
        if candidates:
            # Sort by score (lower is better)
            candidates.sort(key=lambda x: x[5])
            best = candidates[0]
            return open_count, best[0]
        
        # For 100% cases
        if combined.endswith('100'):
            total_count = int(combined[:-3])
            if open_count == total_count:
                return open_count, total_count
    
    # Simple pattern without percentage (e.g., '30/171' or '5/9-')
    simple_match = re.match(r'^(\d+)/(\d+)', text)
    if simple_match:
        return int(simple_match.group(1)), int(simple_match.group(2))
    
    return None, None


def parse_table_row(row, state_name: str):
    """
    Parse a resort row from the new OnTheSnow table layout.
    
    Table columns (as of Dec 2024):
    - Cell 0: Resort name + "X hours ago"
    - Cell 1: 24h snowfall (e.g., "1"-" or "0"-")
    - Cell 2: 3 day snow forecast
    - Cell 3: Base depth + condition (e.g., "19"Variable Conditions")
    - Cell 4: Trails open/total + percentage (e.g., "9/1476% Open" or "30/18816% Open")
    - Cell 5: Lifts open/total (e.g., "5/9-" or "25/35-")
    """
    cells = row.find_all('td')
    if len(cells) < 5:
        return
    
    # Cell 0: Resort name and link
    name_cell = cells[0]
    name_link = name_cell.find('a')
    if not name_link:
        return
    
    # Extract just the resort name (remove "X hours ago" part)
    name_text = name_link.get_text(strip=True)
    # The name often ends with "X hours ago" or "X days ago"
    name = re.sub(r'\d+\s*(hours?|days?|minutes?)\s*ago$', '', name_text, flags=re.IGNORECASE).strip()
    
    resort_url = name_link.get('href', '')
    
    # Generate slug
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    
    # Get coordinates from our lookup table
    lat, lng = RESORT_COORDS.get(slug, (None, None))
    
    # Cell 1: 24h snowfall (format: "1"-" or "0"-")
    new_snow_text = cells[1].get_text(strip=True)
    new_snow_match = re.search(r'(\d+)"', new_snow_text)
    new_snow = int(new_snow_match.group(1)) if new_snow_match else None
    
    # Cell 3: Base depth + condition (format: "19"Variable Conditions" or "16-30"Powder")
    base_text = cells[3].get_text(strip=True)
    # Match patterns like "19"", "16-30"", capturing the first number or range
    base_match = re.search(r'^(\d+)(?:-\d+)?"', base_text)
    base_depth = int(base_match.group(1)) if base_match else None
    
    # Cell 4: Trails (format: "9/1476% Open" or "30/18816% Open" or "-")
    trails_text = cells[4].get_text(strip=True)
    trails_open, trails_total = parse_trails_lifts_text(trails_text)
    
    # Cell 5: Lifts (format: "5/9-" or "25/35-" or "-")
    lifts_text = cells[5].get_text(strip=True) if len(cells) > 5 else ""
    lifts_open, lifts_total = parse_trails_lifts_text(lifts_text)
    
    # Determine if open
    is_open = bool(trails_open and trails_open > 0) or bool(lifts_open and lifts_open > 0)
    
    full_url = urljoin(BASE_URL, resort_url) if resort_url else ''
    
    logger.debug(f"Parsed {name}: {trails_open}/{trails_total} trails, {lifts_open}/{lifts_total} lifts")
    
    # Update or create
    Resort.objects.update_or_create(
        slug=slug,
        defaults={
            'name': name,
            'state': state_name,
            'latitude': lat,
            'longitude': lng,
            'base_depth': base_depth,
            'new_snow_24h': new_snow,
            'trails_open': trails_open,
            'trails_total': trails_total,
            'lifts_open': lifts_open,
            'lifts_total': lifts_total,
            'is_open': is_open,
            'url': full_url,
        }
    )


def parse_resort_row(row, state_name: str):
    """
    Parse a resort row from the old div-based snow report layout (fallback).
    """
    # Extract name and link
    name_elem = row.select_one('a[href*="snow-report"]') or row.select_one('a')
    if not name_elem:
        return
    
    name = name_elem.get_text(strip=True)
    resort_url = name_elem.get('href', '')
    
    # Generate slug
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    
    # Get coordinates from our lookup table
    lat, lng = RESORT_COORDS.get(slug, (None, None))
    
    # Extract snow data from the row
    base_depth = extract_number(row, ['base', 'depth'])
    new_snow = extract_number(row, ['new', '24h', '24hr'])
    
    # Extract trail/lift info
    trails_text = find_text_with_pattern(row, r'(\d+)\s*/\s*(\d+)\s*trails?', r'(\d+)/(\d+)')
    trails_open, trails_total = None, None
    if trails_text:
        match = re.search(r'(\d+)\s*/\s*(\d+)', trails_text)
        if match:
            trails_open, trails_total = int(match.group(1)), int(match.group(2))
    
    lifts_text = find_text_with_pattern(row, r'(\d+)\s*/\s*(\d+)\s*lifts?')
    lifts_open, lifts_total = None, None
    if lifts_text:
        match = re.search(r'(\d+)\s*/\s*(\d+)', lifts_text)
        if match:
            lifts_open, lifts_total = int(match.group(1)), int(match.group(2))
    
    # Determine if open
    is_open = bool(trails_open and trails_open > 0) or bool(lifts_open and lifts_open > 0)
    
    full_url = urljoin(BASE_URL, resort_url) if resort_url else ''
    
    # Update or create
    Resort.objects.update_or_create(
        slug=slug,
        defaults={
            'name': name,
            'state': state_name,
            'latitude': lat,
            'longitude': lng,
            'base_depth': base_depth,
            'new_snow_24h': new_snow,
            'trails_open': trails_open,
            'trails_total': trails_total,
            'lifts_open': lifts_open,
            'lifts_total': lifts_total,
            'is_open': is_open,
            'url': full_url,
        }
    )


def extract_coordinates_from_page(soup, slug: str) -> tuple:
    """
    Try to extract coordinates from resort page.
    Falls back to our lookup table.
    """
    # Check our lookup table first
    if slug in RESORT_COORDS:
        return RESORT_COORDS[slug]
    
    # Try to find in script tags
    for script in soup.find_all('script'):
        text = script.string or ''
        
        # Look for lat/lng patterns
        lat_match = re.search(r'"latitude":\s*([-\d.]+)', text)
        lng_match = re.search(r'"longitude":\s*([-\d.]+)', text)
        
        if lat_match and lng_match:
            try:
                return float(lat_match.group(1)), float(lng_match.group(1))
            except ValueError:
                pass
        
        # Try alternate patterns
        coord_match = re.search(r'center:\s*\[\s*([-\d.]+),\s*([-\d.]+)\s*\]', text)
        if coord_match:
            try:
                return float(coord_match.group(1)), float(coord_match.group(2))
            except ValueError:
                pass
    
    return None, None


def extract_conditions(soup) -> dict:
    """
    Extract condition data from a resort page.
    """
    conditions = {
        'base_depth': None,
        'summit_depth': None,
        'new_snow_24h': None,
        'new_snow_48h': None,
        'trails_open': None,
        'trails_total': None,
        'lifts_open': None,
        'lifts_total': None,
        'is_open': False,
    }
    
    # Look for condition values
    text = soup.get_text()
    
    # Base depth
    base_match = re.search(r'base[:\s]+(\d+)"?', text, re.IGNORECASE)
    if base_match:
        conditions['base_depth'] = int(base_match.group(1))
    
    # New snow
    new_match = re.search(r'new\s+(?:snow\s+)?(\d+)"?\s*(?:in\s+)?(?:24|past)', text, re.IGNORECASE)
    if new_match:
        conditions['new_snow_24h'] = int(new_match.group(1))
    
    # Trails
    trails_match = re.search(r'(\d+)\s*/\s*(\d+)\s*(?:trails|runs)', text, re.IGNORECASE)
    if trails_match:
        conditions['trails_open'] = int(trails_match.group(1))
        conditions['trails_total'] = int(trails_match.group(2))
    
    # Lifts
    lifts_match = re.search(r'(\d+)\s*/\s*(\d+)\s*lifts', text, re.IGNORECASE)
    if lifts_match:
        conditions['lifts_open'] = int(lifts_match.group(1))
        conditions['lifts_total'] = int(lifts_match.group(2))
    
    # Is open
    if conditions['trails_open'] or conditions['lifts_open']:
        conditions['is_open'] = True
    
    return conditions


def extract_number(element, keywords: list) -> Optional[int]:
    """
    Extract a number from text near specified keywords.
    """
    text = element.get_text().lower()
    
    for keyword in keywords:
        # Look for patterns like "24" base" or "base: 24"
        patterns = [
            rf'{keyword}[:\s]+(\d+)',
            rf'(\d+)"?\s*{keyword}',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
    
    return None


def find_text_with_pattern(element, *patterns) -> Optional[str]:
    """
    Find text matching any of the given patterns.
    """
    text = element.get_text()
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    
    return None


def seed_sample_resorts():
    """
    Seed the database with sample resort data for testing.
    Call this if scraping fails or for initial development.
    """
    sample_resorts = [
        {
            'name': 'Vail',
            'slug': 'vail',
            'state': 'Colorado',
            'latitude': 39.6403,
            'longitude': -106.3742,
            'base_depth': 48,
            'new_snow_24h': 6,
            'trails_open': 195,
            'trails_total': 195,
            'lifts_open': 31,
            'lifts_total': 31,
            'is_open': True,
            'url': 'https://www.onthesnow.com/colorado/vail/snow-report.html',
        },
        {
            'name': 'Breckenridge',
            'slug': 'breckenridge',
            'state': 'Colorado',
            'latitude': 39.4817,
            'longitude': -106.0384,
            'base_depth': 42,
            'new_snow_24h': 4,
            'trails_open': 187,
            'trails_total': 187,
            'lifts_open': 35,
            'lifts_total': 35,
            'is_open': True,
            'url': 'https://www.onthesnow.com/colorado/breckenridge/snow-report.html',
        },
        {
            'name': 'Park City',
            'slug': 'park-city',
            'state': 'Utah',
            'latitude': 40.6514,
            'longitude': -111.5080,
            'base_depth': 56,
            'new_snow_24h': 8,
            'trails_open': 341,
            'trails_total': 341,
            'lifts_open': 41,
            'lifts_total': 41,
            'is_open': True,
            'url': 'https://www.onthesnow.com/utah/park-city/snow-report.html',
        },
        {
            'name': 'Mammoth Mountain',
            'slug': 'mammoth-mountain',
            'state': 'California',
            'latitude': 37.6308,
            'longitude': -119.0326,
            'base_depth': 84,
            'new_snow_24h': 12,
            'trails_open': 150,
            'trails_total': 150,
            'lifts_open': 28,
            'lifts_total': 28,
            'is_open': True,
            'url': 'https://www.onthesnow.com/california/mammoth-mountain/snow-report.html',
        },
        {
            'name': 'Jackson Hole',
            'slug': 'jackson-hole',
            'state': 'Wyoming',
            'latitude': 43.5875,
            'longitude': -110.8279,
            'base_depth': 62,
            'new_snow_24h': 5,
            'trails_open': 131,
            'trails_total': 131,
            'lifts_open': 13,
            'lifts_total': 13,
            'is_open': True,
            'url': 'https://www.onthesnow.com/wyoming/jackson-hole/snow-report.html',
        },
        {
            'name': 'Big Sky',
            'slug': 'big-sky',
            'state': 'Montana',
            'latitude': 45.2618,
            'longitude': -111.4015,
            'base_depth': 54,
            'new_snow_24h': 3,
            'trails_open': 300,
            'trails_total': 300,
            'lifts_open': 36,
            'lifts_total': 36,
            'is_open': True,
            'url': 'https://www.onthesnow.com/montana/big-sky/snow-report.html',
        },
        {
            'name': 'Aspen Snowmass',
            'slug': 'aspen-snowmass',
            'state': 'Colorado',
            'latitude': 39.2084,
            'longitude': -106.9490,
            'base_depth': 38,
            'new_snow_24h': 2,
            'trails_open': 337,
            'trails_total': 337,
            'lifts_open': 43,
            'lifts_total': 44,
            'is_open': True,
            'url': 'https://www.onthesnow.com/colorado/aspen-snowmass/snow-report.html',
        },
        {
            'name': 'Steamboat',
            'slug': 'steamboat',
            'state': 'Colorado',
            'latitude': 40.4572,
            'longitude': -106.8045,
            'base_depth': 52,
            'new_snow_24h': 7,
            'trails_open': 169,
            'trails_total': 169,
            'lifts_open': 18,
            'lifts_total': 18,
            'is_open': True,
            'url': 'https://www.onthesnow.com/colorado/steamboat/snow-report.html',
        },
        {
            'name': 'Telluride',
            'slug': 'telluride',
            'state': 'Colorado',
            'latitude': 37.9375,
            'longitude': -107.8123,
            'base_depth': 44,
            'new_snow_24h': 4,
            'trails_open': 148,
            'trails_total': 148,
            'lifts_open': 18,
            'lifts_total': 18,
            'is_open': True,
            'url': 'https://www.onthesnow.com/colorado/telluride/snow-report.html',
        },
        {
            'name': 'Taos',
            'slug': 'taos',
            'state': 'New Mexico',
            'latitude': 36.5969,
            'longitude': -105.4544,
            'base_depth': 36,
            'new_snow_24h': 0,
            'trails_open': 110,
            'trails_total': 110,
            'lifts_open': 14,
            'lifts_total': 15,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-mexico/taos/snow-report.html',
        },
        {
            'name': 'Killington',
            'slug': 'killington',
            'state': 'Vermont',
            'latitude': 43.6045,
            'longitude': -72.8201,
            'base_depth': 32,
            'new_snow_24h': 2,
            'trails_open': 155,
            'trails_total': 155,
            'lifts_open': 22,
            'lifts_total': 22,
            'is_open': True,
            'url': 'https://www.onthesnow.com/vermont/killington/snow-report.html',
        },
        {
            'name': 'Stowe',
            'slug': 'stowe',
            'state': 'Vermont',
            'latitude': 44.5303,
            'longitude': -72.7814,
            'base_depth': 28,
            'new_snow_24h': 3,
            'trails_open': 116,
            'trails_total': 116,
            'lifts_open': 12,
            'lifts_total': 13,
            'is_open': True,
            'url': 'https://www.onthesnow.com/vermont/stowe/snow-report.html',
        },
        {
            'name': 'Jay Peak',
            'slug': 'jay-peak',
            'state': 'Vermont',
            'latitude': 44.9275,
            'longitude': -72.5050,
            'base_depth': 36,
            'new_snow_24h': 5,
            'trails_open': 78,
            'trails_total': 81,
            'lifts_open': 9,
            'lifts_total': 9,
            'is_open': True,
            'url': 'https://www.onthesnow.com/vermont/jay-peak/snow-report.html',
        },
        {
            'name': 'Sugarbush',
            'slug': 'sugarbush',
            'state': 'Vermont',
            'latitude': 44.1357,
            'longitude': -72.9012,
            'base_depth': 24,
            'new_snow_24h': 2,
            'trails_open': 111,
            'trails_total': 111,
            'lifts_open': 16,
            'lifts_total': 16,
            'is_open': True,
            'url': 'https://www.onthesnow.com/vermont/sugarbush/snow-report.html',
        },
        {
            'name': 'Okemo',
            'slug': 'okemo',
            'state': 'Vermont',
            'latitude': 43.4017,
            'longitude': -72.7170,
            'base_depth': 30,
            'new_snow_24h': 3,
            'trails_open': 121,
            'trails_total': 121,
            'lifts_open': 19,
            'lifts_total': 20,
            'is_open': True,
            'url': 'https://www.onthesnow.com/vermont/okemo/snow-report.html',
        },
        {
            'name': 'Stratton',
            'slug': 'stratton',
            'state': 'Vermont',
            'latitude': 43.1136,
            'longitude': -72.9081,
            'base_depth': 26,
            'new_snow_24h': 4,
            'trails_open': 99,
            'trails_total': 99,
            'lifts_open': 11,
            'lifts_total': 11,
            'is_open': True,
            'url': 'https://www.onthesnow.com/vermont/stratton/snow-report.html',
        },
        {
            'name': 'Mount Snow',
            'slug': 'mount-snow',
            'state': 'Vermont',
            'latitude': 42.9601,
            'longitude': -72.9204,
            'base_depth': 22,
            'new_snow_24h': 2,
            'trails_open': 86,
            'trails_total': 86,
            'lifts_open': 20,
            'lifts_total': 20,
            'is_open': True,
            'url': 'https://www.onthesnow.com/vermont/mount-snow/snow-report.html',
        },
        {
            'name': 'Loon Mountain',
            'slug': 'loon-mountain',
            'state': 'New Hampshire',
            'latitude': 44.0364,
            'longitude': -71.6214,
            'base_depth': 28,
            'new_snow_24h': 3,
            'trails_open': 61,
            'trails_total': 61,
            'lifts_open': 10,
            'lifts_total': 11,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-hampshire/loon-mountain/snow-report.html',
        },
        {
            'name': 'Cannon Mountain',
            'slug': 'cannon-mountain',
            'state': 'New Hampshire',
            'latitude': 44.1567,
            'longitude': -71.6986,
            'base_depth': 32,
            'new_snow_24h': 4,
            'trails_open': 97,
            'trails_total': 97,
            'lifts_open': 10,
            'lifts_total': 11,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-hampshire/cannon-mountain/snow-report.html',
        },
        {
            'name': 'Bretton Woods',
            'slug': 'bretton-woods',
            'state': 'New Hampshire',
            'latitude': 44.2586,
            'longitude': -71.4392,
            'base_depth': 26,
            'new_snow_24h': 2,
            'trails_open': 62,
            'trails_total': 63,
            'lifts_open': 10,
            'lifts_total': 10,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-hampshire/bretton-woods/snow-report.html',
        },
        {
            'name': 'Waterville Valley',
            'slug': 'waterville-valley',
            'state': 'New Hampshire',
            'latitude': 43.9506,
            'longitude': -71.5281,
            'base_depth': 24,
            'new_snow_24h': 3,
            'trails_open': 52,
            'trails_total': 52,
            'lifts_open': 8,
            'lifts_total': 11,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-hampshire/waterville-valley/snow-report.html',
        },
        {
            'name': 'Wildcat Mountain',
            'slug': 'wildcat-mountain',
            'state': 'New Hampshire',
            'latitude': 44.2633,
            'longitude': -71.2392,
            'base_depth': 30,
            'new_snow_24h': 5,
            'trails_open': 48,
            'trails_total': 48,
            'lifts_open': 5,
            'lifts_total': 5,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-hampshire/wildcat-mountain/snow-report.html',
        },
        {
            'name': 'Attitash',
            'slug': 'attitash',
            'state': 'New Hampshire',
            'latitude': 44.0828,
            'longitude': -71.2297,
            'base_depth': 22,
            'new_snow_24h': 2,
            'trails_open': 68,
            'trails_total': 68,
            'lifts_open': 9,
            'lifts_total': 11,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-hampshire/attitash/snow-report.html',
        },
        {
            'name': 'Cranmore',
            'slug': 'cranmore',
            'state': 'New Hampshire',
            'latitude': 44.0542,
            'longitude': -71.1086,
            'base_depth': 20,
            'new_snow_24h': 1,
            'trails_open': 57,
            'trails_total': 57,
            'lifts_open': 9,
            'lifts_total': 9,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-hampshire/cranmore/snow-report.html',
        },
        {
            'name': 'Sunday River',
            'slug': 'sunday-river',
            'state': 'Maine',
            'latitude': 44.4736,
            'longitude': -70.8567,
            'base_depth': 34,
            'new_snow_24h': 4,
            'trails_open': 135,
            'trails_total': 135,
            'lifts_open': 18,
            'lifts_total': 18,
            'is_open': True,
            'url': 'https://www.onthesnow.com/maine/sunday-river/snow-report.html',
        },
        {
            'name': 'Sugarloaf',
            'slug': 'sugarloaf',
            'state': 'Maine',
            'latitude': 45.0314,
            'longitude': -70.3131,
            'base_depth': 40,
            'new_snow_24h': 6,
            'trails_open': 162,
            'trails_total': 162,
            'lifts_open': 13,
            'lifts_total': 14,
            'is_open': True,
            'url': 'https://www.onthesnow.com/maine/sugarloaf/snow-report.html',
        },
        {
            'name': 'Whiteface',
            'slug': 'whiteface',
            'state': 'New York',
            'latitude': 44.3656,
            'longitude': -73.9026,
            'base_depth': 28,
            'new_snow_24h': 3,
            'trails_open': 89,
            'trails_total': 89,
            'lifts_open': 11,
            'lifts_total': 11,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-york/whiteface/snow-report.html',
        },
        {
            'name': 'Gore Mountain',
            'slug': 'gore-mountain',
            'state': 'New York',
            'latitude': 43.6717,
            'longitude': -74.0067,
            'base_depth': 24,
            'new_snow_24h': 2,
            'trails_open': 110,
            'trails_total': 110,
            'lifts_open': 14,
            'lifts_total': 14,
            'is_open': True,
            'url': 'https://www.onthesnow.com/new-york/gore-mountain/snow-report.html',
        },
        {
            'name': 'Heavenly',
            'slug': 'heavenly',
            'state': 'California',
            'latitude': 38.9353,
            'longitude': -119.9400,
            'base_depth': 72,
            'new_snow_24h': 10,
            'trails_open': 97,
            'trails_total': 97,
            'lifts_open': 28,
            'lifts_total': 28,
            'is_open': True,
            'url': 'https://www.onthesnow.com/california/heavenly/snow-report.html',
        },
        {
            'name': 'Palisades Tahoe',
            'slug': 'palisades-tahoe',
            'state': 'California',
            'latitude': 39.1969,
            'longitude': -120.2358,
            'base_depth': 96,
            'new_snow_24h': 14,
            'trails_open': 270,
            'trails_total': 270,
            'lifts_open': 42,
            'lifts_total': 42,
            'is_open': True,
            'url': 'https://www.onthesnow.com/california/palisades-tahoe/snow-report.html',
        },
        {
            'name': 'Snowbird',
            'slug': 'snowbird',
            'state': 'Utah',
            'latitude': 40.5830,
            'longitude': -111.6538,
            'base_depth': 78,
            'new_snow_24h': 9,
            'trails_open': 169,
            'trails_total': 169,
            'lifts_open': 13,
            'lifts_total': 14,
            'is_open': True,
            'url': 'https://www.onthesnow.com/utah/snowbird/snow-report.html',
        },
        {
            'name': 'Alta',
            'slug': 'alta',
            'state': 'Utah',
            'latitude': 40.5884,
            'longitude': -111.6386,
            'base_depth': 82,
            'new_snow_24h': 11,
            'trails_open': 116,
            'trails_total': 116,
            'lifts_open': 10,
            'lifts_total': 10,
            'is_open': True,
            'url': 'https://www.onthesnow.com/utah/alta/snow-report.html',
        },
        {
            'name': 'Deer Valley',
            'slug': 'deer-valley',
            'state': 'Utah',
            'latitude': 40.6375,
            'longitude': -111.4783,
            'base_depth': 48,
            'new_snow_24h': 6,
            'trails_open': 103,
            'trails_total': 103,
            'lifts_open': 21,
            'lifts_total': 21,
            'is_open': True,
            'url': 'https://www.onthesnow.com/utah/deer-valley/snow-report.html',
        },
        {
            'name': 'Sun Valley',
            'slug': 'sun-valley',
            'state': 'Idaho',
            'latitude': 43.6806,
            'longitude': -114.4083,
            'base_depth': 40,
            'new_snow_24h': 2,
            'trails_open': 121,
            'trails_total': 121,
            'lifts_open': 17,
            'lifts_total': 18,
            'is_open': True,
            'url': 'https://www.onthesnow.com/idaho/sun-valley/snow-report.html',
        },
        {
            'name': 'Mt. Bachelor',
            'slug': 'mt-bachelor',
            'state': 'Oregon',
            'latitude': 43.9792,
            'longitude': -121.6886,
            'base_depth': 68,
            'new_snow_24h': 8,
            'trails_open': 101,
            'trails_total': 101,
            'lifts_open': 11,
            'lifts_total': 15,
            'is_open': True,
            'url': 'https://www.onthesnow.com/oregon/mt-bachelor/snow-report.html',
        },
        {
            'name': 'Crystal Mountain (WA)',
            'slug': 'crystal-mountain-washington',
            'state': 'Washington',
            'latitude': 46.9282,
            'longitude': -121.5045,
            'base_depth': 88,
            'new_snow_24h': 15,
            'trails_open': 57,
            'trails_total': 57,
            'lifts_open': 10,
            'lifts_total': 11,
            'is_open': True,
            'url': 'https://www.onthesnow.com/washington/crystal-mountain/snow-report.html',
        },
    ]
    
    for resort_data in sample_resorts:
        Resort.objects.update_or_create(
            slug=resort_data['slug'],
            defaults=resort_data
        )
    
    logger.info(f"Seeded {len(sample_resorts)} sample resorts")

