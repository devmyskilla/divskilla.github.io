import requests, json

headers = {'User-Agent': 'Mozilla/5.0'}

# Check freeCodeCamp API for courses
urls = [
    'https://www.freecodecamp.org/api/curriculum',
    'https://www.freecodecamp.org/api/learn',
    'https://www.freecodecamp.org/learn.json',
    'https://api.freecodecamp.org/curriculum',
]

for url in urls:
    try:
        r = requests.get(url, timeout=10, headers=headers)
        print(f'{url} -> {r.status_code}')
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                print(f'  Keys: {list(data.keys())[:5]}')
            elif isinstance(data, list):
                print(f'  Length: {len(data)}')
    except Exception as e:
        print(f'{url} -> {e}')
