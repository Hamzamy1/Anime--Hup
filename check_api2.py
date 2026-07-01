import requests, re

r = requests.get('https://animeslayer.to/title/one-piece-byw', 
                 timeout=15, headers={'User-Agent': 'Mozilla/5.0'})

# Extract inline scripts
scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
for i, script in enumerate(scripts):
    if 'function' in script or 'api' in script.lower() or 'fetch' in script or 'episode' in script:
        print(f"=== Script {i} ===")
        print(script[:2000])
        print()
