"""Thin Claude wrapper that returns text plus the accounting every step logs."""

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    return yaml.safe_load(Path(os.getenv("CONTENTOPS_CONFIG", ROOT / "config.yaml")).read_text())


def is_mock() -> bool:
    return os.getenv("MOCK_MODE", "0") == "1"


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class AgentResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    data: object = None
    detail: dict = field(default_factory=dict)


def cost(agent_cfg: dict, input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * agent_cfg["input_per_mtok"] + output_tokens * agent_cfg["output_per_mtok"]) / 1e6


class Claude:
    def __init__(self, cfg: dict):
        import anthropic

        self.client, self.cfg = anthropic.Anthropic(), cfg

    def __call__(self, agent: str, system: str, prompt: str) -> AgentResult:
        a = self.cfg["agents"][agent]
        t0 = time.perf_counter()
        # Streaming + get_final_message: long posts shouldn't hit HTTP timeouts.
        with self.client.messages.stream(
            model=a["model"],
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": a["effort"]},
        ) as stream:
            resp = stream.get_final_message()
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"{agent}: model refused")
        text = "".join(b.text for b in resp.content if b.type == "text")
        u = resp.usage
        return AgentResult(
            text,
            a["model"],
            u.input_tokens,
            u.output_tokens,
            cost(a, u.input_tokens, u.output_tokens),
            (time.perf_counter() - t0) * 1000,
        )


def parse_json(text: str):
    """Accept bare JSON or a ```json fenced block."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    return json.loads(m.group(1) if m else text)
