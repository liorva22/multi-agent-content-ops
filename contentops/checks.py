"""Deterministic checks: numeric fact verification (part of the fact-checker) and the final-post rubric."""

import re

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
CITATION = re.compile(r"\s?\[F\d+(?:,\s*F\d+)*\]")


def numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in NUMBER.findall(text)}


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def unsupported_numbers(draft: str, sources: str) -> list[dict]:
    """Every number in the draft must appear in the PRD or research notes. Returns one issue per offending sentence."""
    allowed = numbers(sources)
    issues = []
    for s in sentences(CITATION.sub("", draft)):
        bad = sorted(numbers(s) - allowed)
        if bad:
            issues.append({"sentence": s, "problem": f"number(s) {', '.join(bad)} not found in the PRD or research notes"})
    return issues


def _syllables(word: str) -> int:
    groups = re.findall(r"[aeiouy]+", word.lower())
    n = len(groups) - (1 if word.lower().endswith("e") and len(groups) > 1 else 0)
    return max(1, n)


def reading_ease(text: str) -> float:
    words = re.findall(r"[A-Za-z]+", text)
    sents = max(1, len(sentences(text)))
    if not words:
        return 0.0
    return 206.835 - 1.015 * (len(words) / sents) - 84.6 * (sum(map(_syllables, words)) / len(words))


def score_post(post: str, sources: str, cfg: dict) -> dict:
    body = re.sub(r"^#.*$", "", post, flags=re.M)
    words = len(re.findall(r"\b\w+\b", body))
    ease = reading_ease(body)
    checks = {
        "has_title": post.lstrip().startswith("# "),
        "has_tldr": "tl;dr" in post.lower(),
        "enough_sections": len(re.findall(r"^## ", post, re.M)) >= cfg["min_sections"],
        "length_in_range": cfg["min_words"] <= words <= cfg["max_words"],
        "no_citation_markers": not CITATION.search(post),
        "numbers_supported": not unsupported_numbers(post, sources),
        "readable": ease >= cfg["min_reading_ease"],
    }
    return {
        "checks": checks,
        "score": sum(checks.values()) / len(checks),
        "word_count": words,
        "reading_ease": round(ease, 1),
    }
