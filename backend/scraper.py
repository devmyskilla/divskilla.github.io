"""
Automatic course scraper that extracts course data from websites
and adds them to Airtable.

Strategies:
1. Sitemap.xml - Find course URLs from sitemaps
2. JSON-LD - Extract structured data from pages
3. Open Graph - Fallback extraction from meta tags

Usage:
  python scraper.py              # Scrape and add to Airtable
  python scraper.py --dry-run    # Only print what would be added
"""

import os
import sys
import json
import re
import time
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

import urllib.parse
import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

import requests
from bs4 import BeautifulSoup

# ─── Config ────────────────────────────────────────────────────────────────
AIRTABLE_TOKEN = os.getenv('AIRTABLE_API_TOKEN') or ''
AIRTABLE_BASE = os.getenv('AIRTABLE_BASE_ID') or ''
AIRTABLE_TABLE = os.getenv('AIRTABLE_TABLE_NAME', 'Table 1')

SOURCES_FILE = Path(__file__).parent / 'sources.json'
DRY_RUN = '--dry-run' in sys.argv

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; DevMySkillsBot/1.0; +https://devmyskilla.github.io)'
}

# ─── Helpers ───────────────────────────────────────────────────────────────

def log(msg):
    print(f'[scraper] {msg}')

def fetch(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout, headers=HEADERS)
        r.raise_for_status()
        # Fix encoding for sites that serve non-UTF-8 chars
        try:
            r.encoding = r.apparent_encoding or 'utf-8'
        except:
            r.encoding = 'utf-8'
        return r
    except Exception as e:
        log(f'Failed to fetch {url}: {e}')
        return None

def normalize_field(val):
    """Handle Airtable list fields and trim whitespace."""
    if isinstance(val, list):
        val = val[0] if val else ''
    return str(val).strip() if val else ''

# ─── Airtable API ──────────────────────────────────────────────────────────

def get_existing_links():
    """Fetch all existing course links from Airtable."""
    if not AIRTABLE_TOKEN:
        log('No Airtable token configured')
        return set()
    
    links = set()
    url = f'https://api.airtable.com/v0/{AIRTABLE_BASE}/{AIRTABLE_TABLE}'
    headers = {'Authorization': f'Bearer {AIRTABLE_TOKEN}'}
    offset = None

    while True:
        params = {'view': 'Grid view'}
        if offset:
            params['offset'] = offset
        
        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            
            for record in data.get('records', []):
                link = record.get('fields', {}).get('Course Link', '')
                if link:
                    links.add(link.strip())
            
            offset = data.get('offset')
            if not offset:
                break
        except Exception as e:
            log(f'Error fetching Airtable records: {e}')
            break
    
    log(f'Found {len(links)} existing courses in Airtable')
    return links

def add_courses_to_airtable(courses):
    """Add new courses to Airtable in batch."""
    if not courses:
        log('No new courses to add')
        return 0
    
    if DRY_RUN:
        log(f'[DRY RUN] Would add {len(courses)} courses')
        for c in courses:
            print(f'  + {c["name"]} ({c["platform"]})')
        return len(courses)

    url = f'https://api.airtable.com/v0/{AIRTABLE_BASE}/{AIRTABLE_TABLE}'
    headers = {
        'Authorization': f'Bearer {AIRTABLE_TOKEN}',
        'Content-Type': 'application/json',
    }

    # Airtable allows max 10 records per request
    batch_size = 10
    added = 0

    for i in range(0, len(courses), batch_size):
        batch = courses[i:i + batch_size]
        records = {
            'records': [{
                'fields': {
                    'Course Name': c['name'],
                    'Description': c.get('description', ''),
                    'Catgoery': c.get('category', ''),
                    'Plarform': c.get('platform', ''),
                    'Language': c.get('language', 'English'),
                    'Level': c.get('level', 'Beginner'),
                    'Duration': c.get('duration', 'Self-paced'),
                    'Course Link': c.get('link', ''),
                    'Free': c.get('free', True),
                    'Certificate': c.get('certificate', False),
                }
            } for c in batch]
        }

        try:
            r = requests.post(url, headers=headers, json=records, timeout=30)
            r.raise_for_status()
            result = r.json()
            created = len(result.get('records', []))
            added += created
            log(f'Added {created} courses to Airtable')
        except Exception as e:
            log(f'Error adding batch to Airtable: {e}')
    
    return added

# ─── Extraction Strategies ─────────────────────────────────────────────────

def extract_from_sitemap(source):
    """Extract course URLs from a sitemap.xml."""
    log(f'Fetching sitemap: {source["url"]}')
    r = fetch(source['url'])
    if not r:
        return []

    soup = BeautifulSoup(r.text, 'xml')
    urls = []

    # Find all <loc> tags in the sitemap
    for loc in soup.find_all('loc'):
        url = loc.text.strip()
        pattern = source.get('course_url_pattern', '/course/')
        if pattern in url:
            urls.append(url)

    log(f'Found {len(urls)} course URLs in sitemap')
    return urls

def extract_course_from_page(url, platform):
    """Extract course data from a single page using multiple strategies."""
    time.sleep(0.5)  # Be polite
    
    r = fetch(url)
    if not r:
        return None

    soup = BeautifulSoup(r.text, 'lxml')
    course = {
        'link': url,
        'platform': platform,
        'free': True,
        'certificate': False,
        'language': 'English',
        'level': 'Beginner',
        'duration': 'Self-paced',
        'category': '',
        'name': '',
        'description': '',
    }

    # Strategy 1: JSON-LD structured data
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                course['name'] = course['name'] or data.get('name', '')
                course['description'] = course['description'] or data.get('description', '')
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        course['name'] = course['name'] or item.get('name', '')
                        course['description'] = course['description'] or item.get('description', '')
        except:
            pass

    # Strategy 2: Open Graph / Meta tags
    if not course['name']:
        for meta in soup.find_all('meta'):
            prop = meta.get('property', '') or meta.get('name', '')
            content = meta.get('content', '')
            if 'og:title' in prop and content:
                course['name'] = content
            if 'og:description' in prop and content:
                course['description'] = content
            if 'og:image' in prop and content:
                course['thumbnail'] = content
            if 'keywords' in prop.lower() and content:
                course['category'] = content.split(',')[0].strip()

    # Strategy 3: <h1> tag
    if not course['name']:
        h1 = soup.find('h1')
        if h1:
            course['name'] = h1.text.strip()

    # Strategy 4: <title> tag
    if not course['name']:
        title = soup.find('title')
        if title:
            course['name'] = title.text.strip()

    name = course['name']
    # Fix encoding issues: \uFFFD is a replacement character for em dash
    name = name.replace('\uFFFD', '—')
    name = name.replace('\u2014', '—').replace('\u2013', '—')
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Split on known separators and take the longest part (the actual title)
    for sep in [' | ', ' — ', ' – ', ' - ', ' |']:
        if sep in name:
            parts = [p.strip() for p in name.split(sep) if p.strip()]
            if parts:
                # Take the longest part
                name = max(parts, key=len)

    # Remove "—Free Course" or "—Free Online Course" or "—Course" suffixes
    for suffix in ['—Free Online Course', '—Free Course', '—Course', '— Free Course']:
        if suffix in name:
            name = name.split(suffix)[0].strip()

    course['name'] = name.strip().rstrip('—').strip()

    return course

# ─── Main ──────────────────────────────────────────────────────────────────

def load_sources():
    if SOURCES_FILE.exists():
        with open(SOURCES_FILE) as f:
            return json.load(f)
    log('No sources.json found')
    return []

def main():
    log(f'Starting scraper (dry_run={DRY_RUN})')
    
    sources = load_sources()
    if not sources:
        log('No sources configured')
        return

    existing_links = get_existing_links()
    new_courses = []

    for source in sources:
        log(f'\nProcessing source: {source["name"]}')
        
        strategy = source.get('type', 'sitemap')
        platform = source.get('platform', source['name'])

        if strategy == 'sitemap':
            urls = extract_from_sitemap(source)
        else:
            log(f'Unknown strategy: {strategy}')
            continue

        for url in urls:
            if url in existing_links:
                continue

            course = extract_course_from_page(url, platform)
            if course and course['name']:
                new_courses.append(course)
                existing_links.add(url)
                log(f'  Extracted: {course["name"]}')
            else:
                log(f'  Skipped: {url} (no name extracted)')

    total = add_courses_to_airtable(new_courses)
    log(f'\nDone! Added {total} new courses')

if __name__ == '__main__':
    main()
