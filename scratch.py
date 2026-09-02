import urllib.request
import json

url = "https://pddikti.kemdiktisaintek.go.id/api/v2/pt/search/filter?limit=1&page=1"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read().decode('utf-8'))
    
with open("pddikti_test.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
