import requests, re, json
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0'}

# Check HP LIFE catalog/search
urls = [
    'https://www.life-global.org/courses',
    'https://www.life-global.org/search',
    'https://www.life-global.org/catalog',
    'https://www.life-global.org/learn',
]

for url in urls:
    try:
        r = requests.get(url, timeout=10, headers=headers)
        print(f'{url} -> {r.status_code} ({len(r.text)} chars)')
    except Exception as e:
        print(f'{url} -> ERROR: {e}')

# Check freeCodeCamp
r = requests.get('https://www.freecodecamp.org/learn', timeout=10, headers=headers)
print(f'freeCodeCamp learn -> {r.status_code} ({len(r.text)} chars)')

# Find all nav links on HP LIFE homepage
r = requests.get('https://www.life-global.org/', timeout=10, headers=headers)
soup = BeautifulSoup(r.text, 'lxml')
for a in soup.find_all('a'):
    href = a.get('href', '')
    if href and '/course' in href:
        print(f'  Nav link: {href} -> {a.text.strip()[:60]}')
