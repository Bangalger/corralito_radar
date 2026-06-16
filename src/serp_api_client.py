import os

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


def _queries_from_env() -> list[str]:
    raw = os.getenv("NEWS_QUERIES", "").strip()
    if not raw:
        return DEFAULT_QUERIES
    return [q.strip() for q in raw.split("|") if q.strip()]


def _per_query_limit(max_results: int, n_queries: int) -> int:
    if n_queries <= 0:
        return max_results
    return max(2, max_results // n_queries)


def _search_one_query(query: str, api_key: str, num: int) -> list[dict]:
    params = {
        "q": query,
        "tbm": "nws",
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
        text = as_text(news)
        if text:
            items.append(enrich_news_item(text, query=query))
    return items


def fetch_current_news(max_results: int = 8) -> list[dict] | None:
    """
    Busca noticias en Google News vía SerpApi con varias queries,
    deduplica por titular y etiqueta amarillismo por ítem.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key or api_key == "tu_api_key_aqui" or not GoogleSearch:
        return None

    queries = _queries_from_env()
    per_query = _per_query_limit(max_results, len(queries))
    all_items: list[dict] = []

    try:
        for query in queries:
            all_items.extend(_search_one_query(query, api_key, per_query))
        return dedupe_news_items(all_items)[:max_results]
    except Exception as e:
        print(f"Ocurrió un error consultando SerpApi: {e}")
        return None
