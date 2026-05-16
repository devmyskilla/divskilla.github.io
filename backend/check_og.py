import requests
headers = {'User-Agent': 'Mozilla/5.0'}
url = 'https://www.life-global.org/course/343-introduction-to-digital-business-skills'
r = requests.get(url, timeout=10, headers=headers)
print('Encoding:', r.encoding)
print('Apparent:', r.apparent_encoding)
# Check for the character 0xFFFD or em dash
import re
# Find og:title in raw content
raw = r.content
match = re.search(rb'og:title.*?content="([^"]*)"', raw)
if match:
    val = match.group(1)
    print('Raw bytes:', val)
    print('Decoded latin1:', val.decode('latin1'))
    print('Decoded utf-8:', val.decode('utf-8', errors='replace'))
    print('Hex:', val.hex())
