import requests
import pandas as pd
from datetime import datetime, timedelta

from src.mock_data_generator import get_financial_mock_data

SERIES_API_URL = "https://apis.datos.gob.ar/series/api/series"
# Reservas internacionales BCRA (mensual, en millones de USD).
SERIES_RESERVAS_ID = "174.1_RRVAS_IDOS_0_0_36"
# Tasa BADLAR bancos privados (diaria, en %). Proxy vivo de tasa de mercado:
# la "Tasa de Política Monetaria" del BCRA se discontinuó en julio 2025.
SERIES_TASA_ID = "89.2_TS_INTELAR_0_D_20"
RIESGO_PAIS_URL = "https://api.argentinadatos.com/v1/finanzas/indices/riesgo-pais/ultimo"


def _fetch_series_tiempo(
    series_ids: list[str], start_date: str, collapse: str | None = None
) -> dict[str, pd.Series]:
    """Obtiene series de apis.datos.gob.ar y devuelve dict id -> Series (indexada por fecha)."""
    params = {
        "ids": ",".join(series_ids),
        "format": "json",
        "start_date": start_date,
        "limit": "5000",
    }
    if collapse:
        params["collapse"] = collapse
    resp = requests.get(SERIES_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    raw = resp.json()
    if not raw or not raw.get("data"):
        return {}

    result: dict[str, pd.Series] = {}
    for idx, sid in enumerate(series_ids):
        col_idx = idx + 1
        dates, values = [], []
        for row in raw["data"]:
            if row[col_idx] is not None:
                dates.append(pd.Timestamp(row[0]))
                values.append(float(row[col_idx]))
        if dates:
            result[sid] = pd.Series(values, index=dates).sort_index()
    return result


def _align_to_daily(serie: pd.Series, daily_dates: pd.Series) -> list[float]:
    """Alinea una serie (mensual o diaria) sobre el eje de fechas diario con forward/back-fill."""
    if serie.empty:
        return []
    daily_idx = pd.DatetimeIndex(daily_dates)
    # Unimos los índices, rellenamos hacia adelante y luego tomamos solo las fechas diarias.
    combined = serie.reindex(serie.index.union(daily_idx)).ffill().bfill()
    aligned = combined.reindex(daily_idx)
    return aligned.tolist()


def get_riesgo_pais() -> tuple[float | None, bool]:
    """Devuelve (valor en puntos básicos, éxito)."""
    try:
        resp = requests.get(RIESGO_PAIS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        valor = float(data["valor"])
        return valor, True
    except Exception:
        return None, False


def get_real_financial_data(days=90):
    """
    Arma el dataframe financiero de los últimos 'days' usando APIs reales.
    Dólar: ArgentinaDatos (diario). Reservas/Tasa: Series de Tiempo (mensual, fwd-fill).
    Si falla el Dólar, cae al mock completo.
    """
    df_base = get_financial_mock_data(days)
    metadata = {
        "dolar_real": False,
        "bcra_real": False,
        "riesgo_pais": None,
        "riesgo_pais_real": False,
        "error_msg": None,
    }

    # Riesgo país (independiente del dataframe)
    rp_valor, rp_ok = get_riesgo_pais()
    metadata["riesgo_pais"] = rp_valor
    metadata["riesgo_pais_real"] = rp_ok

    # Dólar blue (ArgentinaDatos)
    try:
        url_dolar = "https://api.argentinadatos.com/v1/cotizaciones/dolares/blue"
        res_dolar = requests.get(url_dolar, timeout=10)
        res_dolar.raise_for_status()
        data_dolar = res_dolar.json()

        ultimos_dolar = data_dolar[-days:]
        fechas = [datetime.strptime(item["fecha"], "%Y-%m-%d") for item in ultimos_dolar]
        valores_dolar = [item["venta"] for item in ultimos_dolar]

        _limit = min(len(fechas), len(df_base))
        df_base = df_base.iloc[-_limit:].copy()
        df_base["Fecha"] = fechas[-_limit:]
        df_base["Dólar Blue"] = valores_dolar[-_limit:]
        metadata["dolar_real"] = True

    except Exception as e:
        metadata["error_msg"] = f"Aviso: Dólar API falló ({e}). Usando simulado."
        return df_base, metadata

    # Reservas (mensual) y tasa BADLAR (diaria) vía Series de Tiempo.
    try:
        start_date = (datetime.today() - timedelta(days=200)).strftime("%Y-%m-%d")
        reservas = _fetch_series_tiempo([SERIES_RESERVAS_ID], start_date, collapse="month")
        tasa = _fetch_series_tiempo([SERIES_TASA_ID], start_date)

        got_data = False
        if SERIES_RESERVAS_ID in reservas:
            df_base["Reservas (M USD)"] = _align_to_daily(
                reservas[SERIES_RESERVAS_ID], df_base["Fecha"]
            )
            got_data = True
        if SERIES_TASA_ID in tasa:
            df_base["Tasa BADLAR (%)"] = _align_to_daily(
                tasa[SERIES_TASA_ID], df_base["Fecha"]
            )
            # Mantenemos la clave histórica para el score y compatibilidad.
            df_base["Tasa Política M. (%)"] = df_base["Tasa BADLAR (%)"]
            got_data = True

        if got_data:
            metadata["bcra_real"] = True
            metadata["error_msg"] = None

    except Exception as e:
        metadata["error_msg"] = (
            f"Híbrido: Series de Tiempo falló ({e}). "
            "Usando Dólar real + Reservas/Tasas simuladas."
        )

    return df_base, metadata
