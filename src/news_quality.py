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

_LOCALITY_SIGNALS = (
    r"intendent",
    r"concejal",
    r"concejo deliberante",
    r"municipi",
    r"\bcomuna\b",
    r"\blocalidad\b",
    r"cooperativa",
    r"red de agua",
    r"obras? p[úu]blicas?",
    r"pavimento",
    r"corralito,?\s+c[óo]rdoba",
    r"vecinos?",
)

_FINANCIAL_SIGNALS = (
    r"d[óo]lar",
    r"banco",
    r"bancari",
    r"dep[óo]sit",
    r"\bcepo\b",
    r"default",
    r"\bbcra\b",
    r"reservas",
    r"plazo fijo",
    r"inflaci",
    r"devaluaci",
    r"\bfmi\b",
    r"\bdeuda\b",
    r"\btasa",
    r"brecha",
    r"riesgo pa[íi]s",
    r"retiro",
    r"ahorr",
    r"\bpeso",
    r"cambiari",
    r"\bblue\b",
    r"corrida",
    r"\bmep\b",
    r"\bccl\b",
)

_LOCALITY_RE = re.compile("|".join(_LOCALITY_SIGNALS), re.IGNORECASE)
_FINANCIAL_RE = re.compile("|".join(_FINANCIAL_SIGNALS), re.IGNORECASE)


def _normalize_title(text) -> str:
    head = as_text(text).split(".", 1)[0].strip().lower()
    head = unicodedata.normalize("NFKD", head)
    head = "".join(c for c in head if not unicodedata.combining(c))
    return re.sub(r"\W+", " ", head).strip()


def is_offtopic_locality(text) -> bool:
    """True si la noticia parece referirse a Corralito (localidad) y no a crisis financiera."""
    t = as_text(text)
    if not t or not re.search(r"corralito", t, re.IGNORECASE):
        return False
    if not _LOCALITY_RE.search(t):
        return False
    if _FINANCIAL_RE.search(t):
        return False
    return True


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
    date: str | None = None,
    published: str | None = None,
) -> dict:
    plain = as_text(text)
    s = sensationalism_score(plain)
    if is_offtopic_locality(plain):
        w = 0.0
        status = "offtopic"
    else:
        w = weight_from_score(s)
        status = quality_status(s, w)
    item = {
        "text": plain,
        "query": query,
        "sensationalism": round(s, 3),
        "weight": round(w, 3),
        "status": status,
    }
    if title:
        item["title"] = title
    if link:
        item["link"] = link
    if source:
        item["source"] = source
    pub = date or published
    if pub:
        item["date"] = as_text(pub)
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
                if is_offtopic_locality(plain):
                    normalized["weight"] = 0.0
                    normalized["status"] = "offtopic"
                out.append(normalized)
            else:
                out.append(
                    enrich_news_item(
                        plain,
                        query=item.get("query"),
                        title=item.get("title"),
                        link=item.get("link"),
                        source=item.get("source"),
                        date=item.get("date"),
                        published=item.get("published"),
                    )
                )
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
