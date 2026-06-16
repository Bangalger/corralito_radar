import requests
import urllib3
urllib3.disable_warnings()

def test_bcra():
    url = "https://api.bcra.gob.ar/estadisticas/v2.0/DatosVariable/1" # Reservas is ID 1
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, verify=False)
        print("Status Code v2.0/DatosVariable/1 :", res.status_code)
        if res.status_code == 200:
            print("Data:", res.json())
        else:
            print("Response:", res.text)
    except Exception as e:
        pass
        
    url3 = "https://api.bcra.gob.ar/estadisticas/v3.0/principalesvariables"
    try:
        res = requests.get(url3, headers=headers, verify=False)
        print("Status Code v3.0:", res.status_code)
        if res.status_code == 200:
            print("Success!")
        else:
            print("Response:", res.text)
    except:
        pass

test_bcra()
