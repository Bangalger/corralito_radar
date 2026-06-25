import os
import re
from datetime import datetime, timedelta

from src.news_quality import dedupe_news_items, enrich_news_item
from src.text_utils import as_text

try:
    from serpapi import GoogleSearch
except ImportError:
    GoogleSearch = None

DEFAULT_QUERIES = [
    "crisis económica argentina política monetaria cepo",
    'corralito OR "corralito financiero" argentina',
    "default deuda argentina restricciones cambiarias",
]

RECENCY_DAYS = {
    "d": 1,
    "w": 7,
    "m": 31,
    "y": 365,
}

_SPANISH_MONTHS = {
    "ene": 1,
    "enero": 1,
    "feb": 2,
    "febrero": 2,
    "mar": 3,
    "marzo": 3,
    "abr": 4,
    "abril": 4,
    "may": 5,
    "mayo": 5,
    "jun": 6,
    "junio": 6,
    "jul": 7,
    "julio": 7,
    "ago": 8,
    "agosto": 8,
    "sep": 9,
    "sept": 9,
    "septiembre": 9,
    "set": 9,
    "oct": 10,
    "octubre": 10,
    "nov": 11,
    "noviembre": 11,
    "dic": 12,
    "diciembre": 12,
}

_ENGLISH_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def _queries_from_env() -> list[str]:
    raw = os.getenv("NEWS_QUERIES", "").strip()
    if not raw:
        return DEFAULT_QUERIES
    return [q.strip() for q in raw.split("|") if q.strip()]


def _recency_config() -> tuple[str, int]:
    code = os.getenv("NEWS_RECENCY", "m").strip().lower()
    if code not in RECENCY_DAYS:
        code = "m"
    return code, RECENCY_DAYS[code]


def _per_query_limit(max_results: int, n_queries: int) -> int:
    if n_queries <= 0:
        return max_results
    return max(2, max_results // n_queries)


def _parse_month_name(token: str) -> int | None:
    key = token.strip().lower()
    return _SPANISH_MONTHS.get(key) or _ENGLISH_MONTHS.get(key)


def _parse_absolute_date(s: str) -> datetime | None:
    # DD/MM/YYYY o DD-MM-YYYY
    m = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        for day, month in ((d, mo), (mo, d)):
            try:
                return datetime(y, month, day)
            except ValueError:
                continue

    # "15 oct 2025" / "oct 15, 2025"
    m = re.search(
        r"(\d{1,2})\s+([a-záéíóú]+)\s+(\d{4})",
        s,
        re.IGNORECASE,
    )
    if m:
        month = _parse_month_name(m.group(2))
        if month:
            try:
                return datetime(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                pass

    m = re.search(
        r"([a-záéíóú]+)\s+(\d{1,2}),?\s+(\d{4})",
        s,
        re.IGNORECASE,
    )
    if m:
        month = _parse_month_name(m.group(1))
        if month:
            try:
                return datetime(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass

    return None


def _parse_relative_date(s: str) -> datetime | None:
    now = datetime.now()
    low = s.strip().lower()

    if low in ("hoy", "today"):
        return now
    if low in ("ayer", "yesterday"):
        return now - timedelta(days=1)

    m = re.search(
        r"hace\s+(\d+)\s+(minuto|minutos|hora|horas|d[ií]a|d[ií]as|semana|semanas|mes|meses)",
        low,
    )
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if "minut" in unit:
            return now - timedelta(minutes=n)
        if "hora" in unit:
            return now - timedelta(hours=n)
        if unit.startswith("d"):
            return now - timedelta(days=n)
        if "seman" in unit:
            return now - timedelta(weeks=n)
        if "mes" in unit:
            return now - timedelta(days=n * 30)
        return None

    m = re.search(
        r"hace\s+un[ao]?\s+(minuto|hora|d[ií]a|semana|mes)",
        low,
    )
    if m:
        unit = m.group(1)
        if "minut" in unit:
            return now - timedelta(minutes=1)
        if "hora" in unit:
            return now - timedelta(hours=1)
        if unit.startswith("d"):
            return now - timedelta(days=1)
        if "seman" in unit:
            return now - timedelta(weeks=1)
        if "mes" in unit:
            return now - timedelta(days=30)

    m = re.search(
        r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months)\s+ago",
        low,
    )
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if "minute" in unit:
            return now - timedelta(minutes=n)
        if "hour" in unit:
            return now - timedelta(hours=n)
        if "day" in unit:
            return now - timedelta(days=n)
        if "week" in unit:
            return now - timedelta(weeks=n)
        if "month" in unit:
            return now - timedelta(days=n * 30)

    m = re.search(r"(\d+)\s+(h|hr|hrs|d|w|mo)\b", low)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("h"):
            return now - timedelta(hours=n)
        if unit == "d":
            return now - timedelta(days=n)
        if unit == "w":
            return now - timedelta(weeks=n)
        if unit == "mo":
            return now - timedelta(days=n * 30)

    return None


def parse_news_date(date_str: str) -> datetime | None:
    """Interpreta el campo date de SerpAPI. None si no se puede parsear."""
    s = as_text(date_str)
    if not s:
        return None

    relative = _parse_relative_date(s)
    if relative is not None:
        return relative

    return _parse_absolute_date(s)


def is_within_recency(date_str: str | None, max_days: int) -> bool:
    """
    True si la noticia cae dentro de la ventana de recencia.
    Si no se puede parsear la fecha, se conserva (Google ya filtró con tbs).
    """
    if not date_str:
        return True

    parsed = parse_news_date(date_str)
    if parsed is None:
        # Defensa extra: año explícito claramente viejo (ej. 2025 en 2026).
        year_match = re.search(r"\b(20\d{2})\b", as_text(date_str))
        if year_match:
            year = int(year_match.group(1))
            now = datetime.now()
            if year < now.year:
                return False
            if year == now.year and max_days < 365:
                month_match = re.search(
                    r"\b(ene|enero|feb|febrero|mar|marzo|abr|abril|may|mayo|jun|junio|"
                    r"jul|julio|ago|agosto|sep|sept|septiembre|oct|octubre|nov|noviembre|dic|diciembre|"
                    r"jan|january|feb|february|mar|march|apr|april|may|june|jul|july|aug|august|"
                    r"sep|sept|september|oct|october|nov|november|dec|december)\b",
                    as_text(date_str),
                    re.IGNORECASE,
                )
                if month_match:
                    month = _parse_month_name(month_match.group(1))
                    if month and (now.year, now.month) > (year, month):
                        cutoff = now - timedelta(days=max_days)
                        approx = datetime(year, month, 15)
                        if approx < cutoff:
                            return False
        return True

    cutoff = datetime.now() - timedelta(days=max_days)
    return parsed >= cutoff


def _search_one_query(
    query: str,
    api_key: str,
    num: int,
    recency_code: str,
    max_days: int,
) -> list[dict]:
    params = {
        "q": query,
        "tbm": "nws",
        "tbs": f"qdr:{recency_code}",
        "hl": "es",
        "gl": "ar",
        "api_key": api_key,
        "num": num,
    }
    search = GoogleSearch(params)
    results = search.get_dict()
    news_results = results.get("news_results", [])
    items = []
    for news in news_results:
        title = as_text(news.get("title", ""))
        snippet = as_text(news.get("snippet", ""))
        text = f"{title}. {snippet}".strip(". ") if snippet else title
        if not text:
            text = as_text(news)
        if not text:
            continue

        date_raw = as_text(news.get("date", "")) or None
        if date_raw and not is_within_recency(date_raw, max_days):
            continue

        source_info = news.get("source", {})
        source_name = (
            source_info.get("name", "")
            if isinstance(source_info, dict)
            else as_text(source_info)
        )
        items.append(
            enrich_news_item(
                text,
                query=query,
                title=title or None,
                link=news.get("link") or news.get("url"),
                source=source_name or None,
                date=date_raw,
            )
        )
    return items


def fetch_current_news(max_results: int = 8) -> list[dict] | None:
    """
    Busca noticias en Google News vía SerpApi con varias queries,
    deduplica por titular y etiqueta amarillismo por ítem.

    Retorna None si no hay API key o hay error de red.
    Retorna [] si la API respondió pero no hay noticias dentro de la ventana de recencia.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key or api_key == "tu_api_key_aqui" or not GoogleSearch:
        return None

    recency_code, max_days = _recency_config()
    queries = _queries_from_env()
    per_query = _per_query_limit(max_results, len(queries))
    all_items: list[dict] = []

    try:
        for query in queries:
            all_items.extend(
                _search_one_query(query, api_key, per_query, recency_code, max_days)
            )
        return dedupe_news_items(all_items)[:max_results]
    except Exception as e:
        print(f"Ocurrió un error consultando SerpApi: {e}")
        return None
