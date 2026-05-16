"""
Intelligent course scraper that discovers courses like a human would:
- Searches Google/DuckDuckGo for free courses
- Visits each URL and extracts ALL metadata
- Uses multiple strategies: JSON-LD, OG tags, HTML heuristics
- Optional: Uses Claude API for deep extraction from any page
- Deduplicates against Airtable and adds new courses

Usage:
  python smart_scraper.py                    # Search + scrape + add to Airtable
  python smart_scraper.py --ai               # With AI extraction (needs ANTHROPIC_API_KEY)
  python smart_scraper.py --dry-run          # Preview only
  python smart_scraper.py --url URL          # Scrape a specific URL
"""

import os
import sys
import json
import re
import time
import hashlib
import warnings
from pathlib import Path
from urllib.parse import urlparse, urljoin
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

import requests
from bs4 import BeautifulSoup

# ─── Config ────────────────────────────────────────────────────────────────
AIRTABLE_TOKEN = os.getenv('AIRTABLE_API_TOKEN') or ''
AIRTABLE_BASE = os.getenv('AIRTABLE_BASE_ID') or ''
AIRTABLE_TABLE = os.getenv('AIRTABLE_TABLE_NAME', 'Table 1')
ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY') or ''

SOURCES_FILE = Path(__file__).parent / 'smart_sources.json'
DRY_RUN = '--dry-run' in sys.argv
USE_AI = '--ai' in sys.argv and bool(ANTHROPIC_KEY)
SINGLE_URL = None

for i, arg in enumerate(sys.argv):
    if arg == '--url' and i + 1 < len(sys.argv):
        SINGLE_URL = sys.argv[i + 1]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
}

# ─── Logging ───────────────────────────────────────────────────────────────

def log(msg):
    print(f'  {msg}')

# ─── Airtable ──────────────────────────────────────────────────────────────

def get_existing_links():
    if not AIRTABLE_TOKEN:
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
                    links.add(link.strip().rstrip('/'))
            offset = data.get('offset')
            if not offset:
                break
        except Exception as e:
            log(f'Error fetching Airtable: {e}')
            break
    log(f'📦 Existing courses in Airtable: {len(links)}')
    return links

def add_courses_to_airtable(courses):
    if not courses:
        log('No new courses to add')
        return 0
    if DRY_RUN:
        log(f'📋 [DRY RUN] Would add {len(courses)} courses:')
        for c in courses:
            print(f'     ➕ {c.get("name","?")} ({c.get("platform","?")})')
        return len(courses)

    url = f'https://api.airtable.com/v0/{AIRTABLE_BASE}/{AIRTABLE_TABLE}'
    headers = {'Authorization': f'Bearer {AIRTABLE_TOKEN}', 'Content-Type': 'application/json'}
    batch_size = 10
    added = 0
    for i in range(0, len(courses), batch_size):
        batch = courses[i:i + batch_size]
        records = {'records': [{'fields': {
            'Course Name': c.get('name', ''),
            'Description': c.get('description', ''),
            'Catgoery': c.get('category', ''),
            'Plarform': c.get('platform', ''),
            'Language': c.get('language', 'English'),
            'Level': c.get('level', 'Beginner'),
            'Duration': c.get('duration', 'Self-paced'),
            'Course Link': c.get('link', ''),
            'Free': c.get('free', True),
            'Certificate': c.get('certificate', False),
        }} for c in batch]}
        try:
            r = requests.post(url, headers=headers, json=records, timeout=30)
            r.raise_for_status()
            created = len(r.json().get('records', []))
            added += created
            log(f'✅ Added {created} courses')
        except Exception as e:
            log(f'❌ Error adding batch: {e}')
    return added

# ─── Fetch ─────────────────────────────────────────────────────────────────

def fetch(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout, headers=HEADERS)
        r.raise_for_status()
        try:
            r.encoding = r.apparent_encoding or 'utf-8'
        except:
            r.encoding = 'utf-8'
        return r
    except Exception as e:
        return None

# ─── Intelligent Course Extraction ─────────────────────────────────────────

def extract_course(url):
    """Extract ALL course data from any URL using multiple strategies."""
    r = fetch(url)
    if not r:
        return None

    soup = BeautifulSoup(r.text, 'lxml')
    course = {
        'link': url.rstrip('/'),
        'name': '',
        'description': '',
        'platform': extract_platform(url),
        'category': '',
        'language': '',
        'level': '',
        'duration': '',
        'free': True,
        'certificate': False,
        'thumbnail': '',
    }

    # ── Strategy 1: JSON-LD ──
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    t = item.get('@type', '')
                    if 'Course' in t:
                        course['name'] = course['name'] or item.get('name', '')
                        course['description'] = course['description'] or item.get('description', '')
                        provider = item.get('provider', {})
                        if isinstance(provider, dict):
                            course['platform'] = provider.get('name', course['platform'])
                        offers = item.get('offers', {})
                        if isinstance(offers, dict):
                            price = offers.get('price', '')
                            course['free'] = (price == '0' or offers.get('availability', '') != '')
                    if 'Organization' in t and not course['platform']:
                        course['platform'] = item.get('name', course['platform'])
        except:
            pass

    # ── Strategy 2: Open Graph ──
    for meta in soup.find_all('meta'):
        prop = (meta.get('property', '') or meta.get('name', '')).lower()
        content = meta.get('content', '')
        if 'og:title' in prop and content:
            course['name'] = course['name'] or content
        if 'og:description' in prop and content:
            course['description'] = course['description'] or content
        if 'og:image' in prop and content:
            course['thumbnail'] = course['thumbnail'] or content
        if 'og:site_name' in prop and content:
            course['platform'] = course['platform'] or content
        if 'og:locale' in prop and content:
            lang = content.split('_')[0]
            course['language'] = course['language'] or lang
        if 'author' == prop and content:
            course['platform'] = course['platform'] or content
        if 'keywords' in prop and content and not course['category']:
            cats = [c.strip() for c in content.split(',') if c.strip()]
            if cats:
                course['category'] = cats[0]

    # ── Strategy 3: Twitter Card ──
    for meta in soup.find_all('meta'):
        name = (meta.get('name', '') or '').lower()
        content = meta.get('content', '')
        if 'twitter:title' in name and content:
            course['name'] = course['name'] or content
        if 'twitter:description' in name and content:
            course['description'] = course['description'] or content
        if 'twitter:image' in name and content:
            course['thumbnail'] = course['thumbnail'] or content

    # ── Strategy 4: HTML Heuristics ──
    if not course['name']:
        h1 = soup.find('h1')
        if h1:
            course['name'] = h1.text.strip()
    if not course['name']:
        title = soup.find('title')
        if title:
            course['name'] = title.text.strip()
    if not course['description']:
        for tag in ['p', 'div']:
            els = soup.find_all(tag, class_=re.compile(r'description|summary|about|intro', re.I))
            if els:
                course['description'] = els[0].text.strip()[:500]
                break

    # ── Strategy 5: Detect language from HTML ──
    if not course['language']:
        html = soup.find('html')
        if html:
            lang = html.get('lang', '') or html.get('xml:lang', '') or ''
            if lang and len(lang) <= 5:
                course['language'] = lang.split('-')[0]

    # ── Classify level from text ──
    page_text = soup.get_text(' ', strip=True).lower()
    level_patterns = {
        'Beginner': [r'\bbeginner\b', r'\bintro\b', r'\bfundamental', r'\b101\b', r'\bstart\b', r'\bnew to\b', r'\bentry\b'],
        'Intermediate': [r'\bintermediate\b', r'\badvanced beginner\b', r'\bsome experience\b', r'\bprior knowledge\b'],
        'Advanced': [r'\badvanced\b', r'\bexpert\b', r'\bprofessional\b', r'\bmaster\b', r'\badvanced\b'],
    }
    if not course['level']:
        for level, patterns in level_patterns.items():
            for pat in patterns:
                if re.search(pat, page_text):
                    course['level'] = level
                    break
            if course['level']:
                break

    # ── Detect certificate ──
    if not course['certificate']:
        cert_words = ['certificate', 'certification', 'certified', 'شهادة', 'sertifika', 'badge']
        for word in cert_words:
            if re.search(rf'\b{word}\b', page_text[:2000], re.I):
                course['certificate'] = True
                break

    # ── Detect free/paid ──
    if 'premium' in page_text[:1000].lower() or 'paid' in page_text[:1000].lower():
        course['free'] = False

    # ── Detect duration ──
    dur_patterns = [
        (r'(\d+)\s*(hour|hr|saat|ساعة)', r'\1 hours'),
        (r'(\d+)\s*(week|hafta|أسبوع)', r'\1 weeks'),
        (r'(\d+)\s*(month|ay|شهر)', r'\1 months'),
        (r'(self.?paced|at your own|kendi hızında|حسب وتيرتك)', 'Self-paced'),
    ]
    for pat, replacement in dur_patterns:
        m = re.search(pat, page_text[:3000], re.I)
        if m:
            try:
                num = int(m.group(1))
                if num <= 200:
                    course['duration'] = replacement.replace(r'\1', str(num))
                    if 'self' in pat:
                        course['duration'] = 'Self-paced'
                    break
            except:
                course['duration'] = replacement
                break

    # ── Platform detection from URL ──
    course['platform'] = course['platform'] or extract_platform(url)

    # ── Clean name ──
    course['name'] = clean_name(course['name'])
    if not course['name'] or len(course['name']) < 5:
        return None

    return course

def extract_platform(url):
    domain = urlparse(url).netloc.lower().replace('www.', '')
    known = {
        'life-global.org': 'HP LIFE',
        'freecodecamp.org': 'freeCodeCamp',
        'khanacademy.org': 'Khan Academy',
        'mit.edu': 'MIT OCW',
        'edx.org': 'edX',
        'coursera.org': 'Coursera',
        'udemy.com': 'Udemy',
        'skillshare.com': 'Skillshare',
        'codecademy.com': 'Codecademy',
        'sololearn.com': 'SoloLearn',
        'w3schools.com': 'W3Schools',
        'mozilla.org': 'MDN',
        'developers.google.com': 'Google',
        'learn.microsoft.com': 'Microsoft Learn',
        'alison.com': 'Alison',
        'openculture.com': 'OpenCulture',
        'classcentral.com': 'Class Central',
        'my-mooc.com': 'MyMOOC',
        'futurelearn.com': 'FutureLearn',
        'udacity.com': 'Udacity',
    }
    for d, name in known.items():
        if d in domain:
            return name
    return domain.split('.')[0].title()

def clean_name(name):
    if not name:
        return ''
    name = name.replace('\uFFFD', '—').replace('\u2014', '—').replace('\u2013', '—')
    name = re.sub(r'\s+', ' ', name).strip()

    # Truncate at common separators, keeping the main title
    for sep in [' | ', ' — ', ' – ', ' - ', ' |']:
        if sep in name:
            parts = [p.strip() for p in name.split(sep) if p.strip()]
            if parts:
                name = max(parts, key=len)
    
    # Remove suffixes
    for suffix in ['—Free Online Course', '—Free Course', '—Course', '— Free Course',
                    '- Free Online Course', '- Free Course', '- Free course', '-Free course',
                    '- Free']:
        if suffix in name:
            name = name.split(suffix)[0].strip()

    name = name.strip().rstrip('—').strip()
    if len(name) < 5:
        return ''
    return name

def is_excluded(url, exclude_domains):
    domain = urlparse(url).netloc.lower()
    for ex in exclude_domains:
        if ex in domain:
            return True
    # Exclude non-course pages
    exts = ['.pdf', '.jpg', '.png', '.mp4', '.zip']
    if any(url.lower().endswith(e) for e in exts):
        return True
    return False

def is_course_url(url):
    """Heuristic: check if URL looks like a course page."""
    path = urlparse(url).path.lower()
    indicators = ['/course/', '/learn/', '/class/', '/training/', '/tutorial/',
                  '/module/', '/lesson/', '/path/', '/program/', '/specialization/',
                  '/certification/', '/workshop/', '/bootcamp/', '/nanodegree/']
    for ind in indicators:
        if ind in path:
            return True
    # If no indicator, check page content later
    return None  # Unsure, will check content

# ─── AI Extraction (Optional) ─────────────────────────────────────────────

def extract_with_ai(url):
    """Use Claude API to extract course data from any URL."""
    if not ANTHROPIC_KEY:
        return None

    r = fetch(url, timeout=30)
    if not r:
        return None

    soup = BeautifulSoup(r.text, 'lxml')
    # Clean the page text
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    text = soup.get_text(' ', strip=True)[:8000]

    prompt = f"""Extract course information from this webpage content. Return ONLY valid JSON with these fields:
- name (course title)
- description (short description, max 200 chars)
- platform (website/school name)
- category (subject area: e.g. Programming, Marketing, Business, Design, etc.)
- language (e.g. English, Arabic, Turkish)
- level (Beginner, Intermediate, or Advanced)
- duration (e.g. "Self-paced", "4 weeks", "10 hours")
- free (true/false)
- certificate (true/false - does it offer a certificate upon completion)

URL: {url}

Page content:
{text[:7000]}

Return ONLY valid JSON, no other text:"""

    try:
        r = requests.post('https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-3-haiku-20240307',
                'max_tokens': 500,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )
        r.raise_for_status()
        data = r.json()
        content = data['content'][0]['text']
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        log(f'⚠️ AI extraction failed: {e}')
    return None

# ─── Search ────────────────────────────────────────────────────────────────

def search_courses(query, max_results=10):
    """Search DuckDuckGo for free courses."""
    try:
        from duckduckgo_search import DDGS
        log(f'🔍 Searching: "{query}"')
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    'title': r.get('title', ''),
                    'href': r.get('href', ''),
                    'body': r.get('body', ''),
                })
        time.sleep(1)  # Be polite
        return results
    except Exception as e:
        log(f'⚠️ Search failed: {e}')
        return []

def load_sources():
    if SOURCES_FILE.exists():
        with open(SOURCES_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {'queries': ['free online courses'], 'exclude_domains': ['facebook.com', 'twitter.com', 'instagram.com']}

# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    print('\n' + '=' * 60)
    print('  🎓 DevMySkills Smart Course Scraper')
    print('=' * 60)

    if SINGLE_URL:
        print(f'\n📌 Scraping single URL: {SINGLE_URL}\n')
        course = extract_course(SINGLE_URL)
        if USE_AI:
            ai_data = extract_with_ai(SINGLE_URL)
            if ai_data:
                course.update(ai_data)

        if course and course['name']:
            print(f'  📖 Name: {course["name"]}')
            print(f'  📝 Description: {course["description"][:100]}...')
            print(f'  🏫 Platform: {course["platform"]}')
            print(f'  📂 Category: {course["category"]}')
            print(f'  🌐 Language: {course["language"]}')
            print(f'  📊 Level: {course["level"]}')
            print(f'  ⏱ Duration: {course["duration"]}')
            print(f'  💰 Free: {"✅" if course["free"] else "❌"}')
            print(f'  🏅 Certificate: {"✅" if course["certificate"] else "❌"}')
        else:
            print('  ❌ Could not extract course data from this URL')
        return

    sources = load_sources()
    queries = sources.get('queries', [])
    exclude_domains = sources.get('exclude_domains', [])

    print(f'\n📋 Loaded {len(queries)} search queries')
    print(f'🚫 Excluding {len(exclude_domains)} domains\n')

    existing_links = get_existing_links()
    discovered_urls = set()
    all_new_courses = []

    # ── Search Phase ──
    print('\n─── Search Phase ───')
    for query in queries:
        results = search_courses(query, max_results=8)
        for r in results:
            url = r['href'].rstrip('/')
            if url in existing_links or url in discovered_urls:
                continue
            if is_excluded(url, exclude_domains):
                continue

            # Quick check if it looks like a course page
            url_check = is_course_url(url)
            if url_check is False:
                continue

            discovered_urls.add(url)

    print(f'\n🔗 Discovered {len(discovered_urls)} unique URLs to analyze')

    # ── Extraction Phase ──
    print('\n─── Extraction Phase ───')
    urls_list = list(discovered_urls)
    for i, url in enumerate(urls_list, 1):
        print(f'\n[{i}/{len(urls_list)}] {url[:80]}...')
        
        course = extract_course(url)
        if USE_AI and course:
            ai_data = extract_with_ai(url)
            if ai_data:
                course.update(ai_data)

        if course and course['name']:
            all_new_courses.append(course)
            print(f'  ✅ {course["name"]} ({course["platform"]})')
        else:
            print(f'  ⏭ Skipped (not a course page)')
        
        if i < len(urls_list):
            time.sleep(1.5)  # Rate limiting

    # ── Add to Airtable ──
    print(f'\n─── Results ───')
    print(f'   🔍 Searches: {len(queries)}')
    print(f'   🌐 URLs discovered: {len(discovered_urls)}')
    print(f'   📚 New courses found: {len(all_new_courses)}')

    total = add_courses_to_airtable(all_new_courses)
    print(f'\n{"=" * 60}')
    print(f'  ✅ Done! Added {total} new courses to Airtable')
    print(f'{"=" * 60}\n')

if __name__ == '__main__':
    main()
