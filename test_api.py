import requests
import json

def find_endpoints():
    try:
        res = requests.get("https://api.argentinadatos.com/openapi.json")
        spec = res.json()
        paths = spec.get('paths', {}).keys()
        
        print("--- ArgentinaDatos Endpoints ---")
        for p in paths:
            if 'reservas' in p.lower() or 'tasa' in p.lower() or 'bcra' in p.lower() or 'leliq' in p.lower() or 'politic' in p.lower():
                print(p)
                
    except Exception as e:
        print(f"Error: {e}")

find_endpoints()
