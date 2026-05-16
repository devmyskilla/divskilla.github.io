import requests, re, json
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0'}

url = 'https://www.life-global.org/course/390-customer-experience-(cx)-for-business-success'
r = requests.get(url, timeout=15, headers=headers)
soup = BeautifulSoup(r.text, 'lxml')

scripts = soup.find_all('script')
print(f'Found {len(scripts)} script tags')

for i, script in enumerate(scripts):
    src = script.get('src', '')
    text = (script.string or '')[:200].replace('\n', ' ')
    if text.strip() or src:
        print(f'\n[{i}] src="{src[:80]}" | text="{text[:150]}"')
