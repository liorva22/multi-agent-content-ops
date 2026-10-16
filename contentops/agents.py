"""The four agents. `ClaudeAgents` prompts real models; `MockAgents` is a deterministic offline stand-in."""

import json
import re
import time

from .checks import CITATION, sentences, unsupported_numbers
from .llm import AgentResult, Claude, approx_tokens, cost, parse_json

RESEARCHER = (
    "You are a meticulous research analyst. Extract every concrete, checkable fact from the PRD (numbers, dates, "
    "names, scope, non-goals). Do not add outside facts. Return a JSON array of objects "
    '{"id": "F1", "claim": "...", "source": "PRD: <section>"} and nothing else.'
)
WRITER = (
    "You are a product marketing writer. Write a blog post announcing the feature, in Markdown: a '# ' title, "
    "an intro, and at least three '## ' sections, 450-800 words. Use ONLY the facts provided; never invent "
    "numbers, customers or quotes. After every sentence that uses a fact, cite it like [F3]."
)
FACT_CHECKER = (
    "You are a strict fact-checker. Compare each claim in the draft against the numbered facts and the PRD. "
    "Flag anything unsupported, exaggerated or contradicted. Return JSON "
    '{"issues": [{"sentence": "...", "problem": "..."}]} with an empty list if the draft is accurate.'
)
POLISHER = (
    "You are a copy editor. Polish the draft to our style guide: keep every fact and number exactly as written; "
    "remove the [F#] citation markers; keep the '# ' title and '## ' sections; add a one-sentence '**TL;DR:**' "
    "line directly under the title; prefer active voice and short sentences; no hype words like 'revolutionary'. "
    "Return only the final Markdown."
)
JUDGE = (
    "Rate this blog post 1-5 on each of: clarity, accuracy_to_prd, engagement. "
    'Return JSON {"clarity": n, "accuracy_to_prd": n, "engagement": n}.'
)


class ClaudeAgents:
    def __init__(self, cfg: dict):
        self.llm = Claude(cfg)

    def research(self, prd: str) -> AgentResult:
        r = self.llm("researcher", RESEARCHER, prd)
        r.data = parse_json(r.text)
        return r

    def write(self, prd: str, facts: list, feedback: list | None, attempt: int) -> AgentResult:
        prompt = f"PRD:\n{prd}\n\nFacts:\n{json.dumps(facts, indent=1)}"
        if feedback:
            prompt += "\n\nYour previous draft failed fact-checking. Fix these issues:\n" + json.dumps(feedback, indent=1)
        return self.llm("writer", WRITER, prompt)

    def fact_check(self, prd: str, facts: list, draft: str) -> AgentResult:
        r = self.llm("fact_checker", FACT_CHECKER, f"PRD:\n{prd}\n\nFacts:\n{json.dumps(facts)}\n\nDraft:\n{draft}")
        llm_issues = parse_json(r.text).get("issues", [])
        num_issues = unsupported_numbers(draft, prd + json.dumps(facts))
        r.data = llm_issues + num_issues
        r.detail = {"llm_issues": len(llm_issues), "numeric_issues": len(num_issues)}
        return r

    def polish(self, draft: str) -> AgentResult:
        return self.llm("polisher", POLISHER, draft)

    def judge(self, prd: str, post: str) -> AgentResult:
        r = self.llm("judge", JUDGE, f"PRD:\n{prd}\n\nPost:\n{post}")
        r.data = parse_json(r.text)
        return r


def _section(prd: str, name: str) -> str:
    m = re.search(rf"^## {name}\s*\n(.*?)(?=^## |\Z)", prd, re.S | re.M | re.I)
    return m.group(1).strip() if m else ""


class MockAgents:
    """Offline, deterministic agents built from the PRD text with templates.

    The mock writer is *scripted* to slip an invented statistic into its first N drafts (N per PRD title below,
    default 0), so the fact-check -> rollback -> rewrite path runs in the demo and in CI.
    """

    HALLUCINATION = "Early customers also reported a 37% jump in overall team productivity."
    SCRIPTED_HALLUCINATIONS = {"Smart Inbox Triage": 1, "Usage-Based Billing Dashboard": 2}

    def __init__(self, cfg: dict, hallucinations: dict | None = None):
        self.cfg = cfg
        self.hallucinations = self.SCRIPTED_HALLUCINATIONS if hallucinations is None else hallucinations

    def _result(self, agent: str, inp: str, text: str, t0: float, data=None) -> AgentResult:
        a = self.cfg["agents"][agent]
        i, o = approx_tokens(inp), approx_tokens(text)
        # "mock:" prefix so nobody reads a mock step as a real model call.
        return AgentResult(text, f"mock:{a['model']}", i, o, cost(a, i, o), (time.perf_counter() - t0) * 1000, data)

    def research(self, prd: str) -> AgentResult:
        t0 = time.perf_counter()
        facts = []
        for sec in ("Summary", "Problem", "Solution", "Beta results", "Launch", "Non-goals"):
            for s in sentences(re.sub(r"^- ", "", _section(prd, sec), flags=re.M)):
                facts.append({"id": f"F{len(facts) + 1}", "claim": s, "source": f"PRD: {sec}"})
        return self._result("researcher", RESEARCHER + prd, json.dumps(facts, indent=1), t0, facts)

    def write(self, prd: str, facts: list, feedback: list | None, attempt: int) -> AgentResult:
        t0 = time.perf_counter()
        title = re.search(r"^# (?:PRD:\s*)?(.+)$", prd, re.M).group(1).strip()
        by_src = {}
        for f in facts:
            by_src.setdefault(f["source"].split(": ", 1)[1], []).append(f)

        def para(sec, lead=""):
            return lead + " ".join(f"{f['claim']} [{f['id']}]" for f in by_src.get(sec, []))

        parts = [
            f"# Introducing {title}",
            para("Summary"),
            "## The problem we set out to solve",
            para("Problem"),
            "## How it works",
            para("Solution"),
            "## What the beta showed",
            para("Beta results", "We tested it with real customers before launch. "),
            "## Availability",
            para("Launch"),
            "## What it doesn't do (yet)",
            para("Non-goals", "To keep the scope tight, these are out of scope for now: "),
        ]
        if attempt <= self.hallucinations.get(title, 0):
            parts[7] += " " + self.HALLUCINATION
        text = "\n\n".join(parts)
        return self._result("writer", WRITER + prd + json.dumps(facts) + json.dumps(feedback or []), text, t0)

    def fact_check(self, prd: str, facts: list, draft: str) -> AgentResult:
        t0 = time.perf_counter()
        issues = unsupported_numbers(draft, prd + json.dumps(facts))
        r = self._result("fact_checker", FACT_CHECKER + prd + draft, json.dumps({"issues": issues}), t0, issues)
        r.detail = {"llm_issues": 0, "numeric_issues": len(issues)}
        return r

    def polish(self, draft: str) -> AgentResult:
        t0 = time.perf_counter()
        text = CITATION.sub("", draft)
        lines = text.split("\n\n")
        tldr = sentences(lines[1])[0] if len(lines) > 1 and lines[1] else ""
        text = "\n\n".join([lines[0], f"**TL;DR:** {tldr}", *lines[1:]])
        return self._result("polisher", POLISHER + draft, text, t0)

    def judge(self, prd: str, post: str):
        return None  # no fake quality scores in mock mode
