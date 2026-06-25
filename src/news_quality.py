import re
import unicodedata

from src.text_utils import as_text

EXCLUDE_THRESHOLD = 0.85
WARN_THRESHOLD = 0.45

_CLICKBAIT_PHRASES = (
    r"¿viene el\b",
    r"¿vuelve el\b",
    r"¿est[aá] por venir\b",
    r"exclusivo",
    r"urgente\b",
    r"último momento",
    r"ultimo momento",
    r"alerta roja",
    r"bomba\b",
    r"inminente",
    r"apocalipsis",
    r"fin del mundo",
    r"no te lo vas a creer",
    r"expertos en shock",
    r"se desata",
    r"caos total",
    r"p[aá]nico total",
    r"esc[aá]ndalo",
    r"revelaci[oó]n",
    r"impactante",
    r"sin precedentes",
    r"hist[oó]rico\b",
    r"breaking",
)

_CLICKBAIT_RE = re.compile("|".join(_CLICKBAIT_PHRASES), re.IGNORECASE)


def _normalize_title(text) -> str:
    head = as_text(text).split(".", 1)[0].strip().lower()
    head = unicodedata.normalize("NFKD", head)
    head = "".join(c for c in head if not unicodedata.combining(c))
    return re.sub(r"\W+", " ", head).strip()


def sensationalism_score(text) -> float:
    t = as_text(text)
    if not t:
        return 0.0

    score = 0.0
    if t.count("?") >= 2 or t.count("!") >= 2:
        score += 0.2
    if t.startswith("¿") or "¿" in t[:40]:
        score += 0.15

    words = re.findall(r"\b[\wáéíóúñÁÉÍÓÚÑ]+\b", t)
    if words:
        caps = sum(1 for w in words if len(w) > 3 and w.isupper())
        if caps / len(words) > 0.15:
            score += 0.25

    matches = len(_CLICKBAIT_RE.findall(t))
    score += min(0.15 * matches, 0.45)

    if re.search(r"corralito", t, re.IGNORECASE) and _CLICKBAIT_RE.search(t):
        score += 0.1

    return min(score, 1.0)


def weight_from_score(sensationalism: float) -> float:
    if sensationalism >= EXCLUDE_THRESHOLD:
        return 0.0
    if sensationalism <= WARN_THRESHOLD:
        return 1.0
    span = EXCLUDE_THRESHOLD - WARN_THRESHOLD
    return 1.0 - (sensationalism - WARN_THRESHOLD) / span


def quality_status(sensationalism: float, weight: float) -> str:
    if weight == 0.0:
        return "excluded"
    if sensationalism > WARN_THRESHOLD:
        return "reduced"
    return "ok"


def enrich_news_item(
    text,
    query: str | None = None,
    title: str | None = None,
    link: str | None = None,
    source: str | None = None,
) -> dict:
    plain = as_text(text)
    s = sensationalism_score(plain)
    w = weight_from_score(s)
    item = {
        "text": plain,
        "query": query,
        "sensationalism": round(s, 3),
        "weight": round(w, 3),
        "status": quality_status(s, w),
    }
    if title:
        item["title"] = title
    if link:
        item["link"] = link
    if source:
        item["source"] = source
    return item


def enrich_news_batch(texts: list, query: str | None = None) -> list[dict]:
    return [enrich_news_item(t, query=query) for t in texts if as_text(t)]


def normalize_news_items(items: list) -> list[dict]:
    if not items:
        return []
    out: list[dict] = []
    for item in items:
        if isinstance(item, str):
            out.append(enrich_news_item(item))
        elif isinstance(item, dict):
            plain = as_text(item.get("text", item))
            if not plain:
                continue
            if "weight" in item and "sensationalism" in item:
                normalized = dict(item)
                normalized["text"] = plain
                out.append(normalized)
            else:
                out.append(enrich_news_item(plain, query=item.get("query")))
    return dedupe_news_items(out)


def dedupe_news_items(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        plain = as_text(item.get("text", ""))
        if not plain:
            continue
        item = dict(item)
        item["text"] = plain
        key = _normalize_title(plain)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
