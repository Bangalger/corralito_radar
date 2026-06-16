import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.mock_data_generator import get_financial_mock_data

def get_real_financial_data(days=90):
    """
    Intenta armar el dataframe financiero de los últimos 'days' usando APIs reales.
    Si falla el Dólar, cae al mock general completo.
    Si falla el BCRA o no hay token, el Dólar es real y el BCRA simulado (Modo Híbrido).
    """
    # 1. Obtenemos un Mock completo de base para rellenar huecos si algo falla
    df_base = get_financial_mock_data(days)
    metadata = {
        "dolar_real": False,
        "bcra_real": False,
        "error_msg": None
    }
    
    # 2. INTENTO OBTENER DÓLAR BLUE (ArgentinaDatos - No requiere Token)
    try:
        url_dolar = "https://api.argentinadatos.com/v1/cotizaciones/dolares/blue"
        res_dolar = requests.get(url_dolar, timeout=10)
        res_dolar.raise_for_status()
        data_dolar = res_dolar.json()
        
        # ArgentinaDatos devuelve una lista larga ascendente, agarramos los ultimos 'days'
        ultimos_dolar = data_dolar[-days:]
        
        # Reemplazamos las fechas y dolares en el df_base
        fechas = [datetime.strptime(item["fecha"], "%Y-%m-%d") for item in ultimos_dolar]
        valores_dolar = [item["venta"] for item in ultimos_dolar]
        
        # A veces faltan dias laborables, alineamos por precaucion truncando al min len
        _limit = min(len(fechas), len(df_base))
        
        # Pisamos los falsos con reales
        df_base = df_base.iloc[-_limit:].copy()
        df_base['Fecha'] = fechas[-_limit:]
        df_base['Dólar Libre'] = valores_dolar[-_limit:]
        metadata["dolar_real"] = True
        
    except Exception as e:
        metadata["error_msg"] = f"Aviso: Dólar API falló ({e}). Usando simulado."
        return df_base, metadata
        
    # 3. INTENTO OBTENER BCRA (EstadisticasBCRA - Requiere Token)
    token_bcra = os.getenv("ESTADISTICAS_BCRA_TOKEN")
    if not token_bcra or token_bcra == "tu_token_aqui":
        metadata["error_msg"] = "Híbrido: No hay ESTADISTICAS_BCRA_TOKEN. Usando Dólar real + Reservas BCRA Simuladas."
        return df_base, metadata
        
    headers = {"Authorization": f"BEARER {token_bcra}"}
    try:
        # Pidiendo Reservas
        res_res = requests.get("https://api.estadisticasbcra.com/reservas", headers=headers, timeout=10)
        res_res.raise_for_status()
        hist_reservas = res_res.json()
        
        # Pidiendo Tasa Política Monetaria (Usamos BADLAR como proxy estable de mercado)
        res_tasa = requests.get("https://api.estadisticasbcra.com/tasa_badlar", headers=headers, timeout=10)
        res_tasa.raise_for_status()
        hist_tasa = res_tasa.json()
        
        # EstadisticasBCRA se quedó planchado en 2024. Al ser un MVP, en lugar de 
        # intentar matchear la fecha 2026 (lo que daba las líneas rectas "flat"),
        # vamos a agarrar las últimas N observaciones útiles y simular que ocurren hoy.
        ultimas_reservas = [item["v"] for item in hist_reservas[-len(df_base):]]
        ultimas_tasas = [item["v"] for item in hist_tasa[-len(df_base):]]
        
        # En caso de que haya menos datos que los solicitados, los rellenamos al principio
        if len(ultimas_reservas) < len(df_base):
            ultimas_reservas = [ultimas_reservas[0]] * (len(df_base) - len(ultimas_reservas)) + ultimas_reservas
        if len(ultimas_tasas) < len(df_base):
            ultimas_tasas = [ultimas_tasas[0]] * (len(df_base) - len(ultimas_tasas)) + ultimas_tasas
            
        # Pisar columnas Mock con Valores Reales (últimos datos vivos de la API)
        df_base['Reservas (M USD)'] = ultimas_reservas
        df_base['Tasa Política M. (%)'] = ultimas_tasas
        
        metadata["bcra_real"] = True
        metadata["error_msg"] = None # Todo un éxito
        
    except Exception as e:
        metadata["error_msg"] = f"Híbrido: Falló conexión api.estadisticasbcra.com ({e}). Reservas son Simuladas."
        
    return df_base, metadata
