"""Conversión robusta de respuestas SerpApi / legacy a texto plano."""


def as_text(value, _seen: set[int] | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()

    if _seen is None:
        _seen = set()
    obj_id = id(value)
    if obj_id in _seen:
        return ""
    _seen.add(obj_id)

    if isinstance(value, dict):
        title = as_text(value.get("title"), _seen)
        snippet = as_text(value.get("snippet"), _seen)
        text_field = value.get("text")
        body = as_text(text_field, _seen) if text_field is not None else ""
        if body:
            return body
        if title and snippet:
            return f"{title}. {snippet}".strip(". ")
        return title or snippet

    if isinstance(value, (list, tuple)):
        parts = [as_text(v, _seen) for v in value]
        return " ".join(p for p in parts if p)

    return str(value).strip()
