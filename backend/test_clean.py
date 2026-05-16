# Test the name cleaning
import re

test = 'How To Succeed in the Digital Era\u2013Free Course | HP LIFE'
print('Original:', repr(test))

name = test
name = name.replace('\uFFFD', '—')
name = name.replace('\u2014', '—').replace('\u2013', '—')
name = re.sub(r'\s+', ' ', name).strip()

for sep in [' | ', ' — ', ' – ', ' - ', ' |']:
    if sep in name:
        parts = [p.strip() for p in name.split(sep) if p.strip()]
        if parts:
            name = max(parts, key=len)

name = name.strip().rstrip('—').strip()
print('Cleaned:', repr(name))
print('Display:', name)
