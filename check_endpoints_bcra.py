import requests
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("ESTADISTICAS_BCRA_TOKEN")

if token:
    headers = {"Authorization": f"BEARER {token}"}
    try:
        # Algunos endpoints de APIs REST devuelven un directorio vivo si le pegas al base url.
        res = requests.get("https://api.estadisticasbcra.com/api", headers=headers)
        print("Status Base:", res.status_code)
        if res.status_code == 200:
            print("Content:", res.json())
            
        # Intentemos 'badlar', 'tasas', 'tasa_pm'
        for ep in ['badlar', 'tasa_badlar', 'cer', 'tasa_leliq', 'leliq']:
            res = requests.get(f"https://api.estadisticasbcra.com/{ep}", headers=headers)
            if res.status_code == 200:
                print(f"Endpoint '{ep}' EXISTE y responde 200.")
            else:
                print(f"Endpoint '{ep}' error: {res.status_code}")
                
    except Exception as e:
        print("Error:", e)
else:
    print("Token no encontrado.")
