import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def get_financial_mock_data(days=90):
    """Genera datos simulados para el MVP del dashboard."""
    dates = [datetime.today() - timedelta(days=i) for i in range(days)]
    dates.reverse()
    
    # Reservas (tendencia a la baja simulando crisis de los ultimos dias)
    reservas = np.linspace(25000, 20000, days) + np.random.normal(0, 500, days)
    # Dólar blue (tendencia a la suba con saltos al final)
    dolar = np.linspace(1000, 1500, days) + np.random.normal(0, 50, days)
    # Tasa (Aumenta de repente como reaccion del BCRA)
    tasas = np.full(days, 80.0)
    tasas[-20:] = 100.0 # Salto en los ultimos 20 dias
    tasas[-5:] = 130.0   # Panico en los ultimos 5
    
    df = pd.DataFrame({
        'Fecha': dates,
        'Reservas (M USD)': reservas,
        'Dólar Libre': dolar,
        'Tasa Política M. (%)': tasas
    })
    return df

def get_mock_news():
    """Noticias simuladas para testear NLP sin gastar SerpApi."""
    from src.news_quality import dedupe_news_items, enrich_news_item

    raw = [
        {
            "query": "crisis económica argentina política monetaria cepo",
            "text": "El gobierno asegura que el que depositó dólares los recibirá pronto y no hay riesgo sistémico.",
            "source": "Infobae (mock)",
            "link": None,
        },
        {
            "query": "crisis económica argentina política monetaria cepo",
            "text": "Se frena la liquidación del agro esperando un mejor tipo de cambio por la brecha.",
            "source": "Ambito (mock)",
            "link": None,
        },
        {
            "query": "crisis económica argentina política monetaria cepo",
            "text": "El Banco Central sube fuerte la tasa de interés para contener la corrida al dólar libre.",
            "source": "La Nación (mock)",
            "link": None,
        },
        {
            "query": 'corralito OR "corralito financiero" argentina',
            "text": "Cacerolazos en distintos puntos de la ciudad por el aumento de tarifas y corralito encubierto.",
            "source": "Clarín (mock)",
            "link": None,
        },
        {
            "query": 'corralito OR "corralito financiero" argentina',
            "text": "¿Viene el corralito? ¡EXCLUSIVO! Expertos en shock por el dólar y el caos total en los bancos.",
            "source": "Cronista (mock)",
            "link": None,
        },
        {
            "query": "default deuda argentina restricciones cambiarias",
            "text": "Empresarios piden calma mientras el riesgo país vuelve a tocar nuevos récords históricos.",
            "source": "El Economista (mock)",
            "link": None,
        },
    ]
    items = [enrich_news_item(r["text"], query=r["query"], source=r["source"], link=r["link"]) for r in raw]
    return dedupe_news_items(items)
