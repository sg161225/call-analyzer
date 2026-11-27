"""Cerebras: a second free AI provider, used when Groq's limits are reached (optional: needs CEREBRAS_API_KEY).

Cerebras has an OpenAI-style API, called here with httpx (already installed with the Groq library), so no
extra package is needed. The models available to the key are read from the account itself.
"""
from __future__ import annotations

import os
import re
import time

import httpx

BASE = "https://api.cerebras.ai/v1"
PREFERRED = ["gpt-oss-120b", "qwen-3-235b-a22b-instruct-2507", "llama-3.3-70b", "zai-glm-4.6", "qwen-3-32b",
             "llama-4-scout-17b-16e-instruct", "llama3.1-8b"]
_SKIP = ("whisper", "embed", "guard", "tts")
_CACHE: dict = {"at": 0.0, "ids": None}
MAX_MODELS = 3


class CerebrasFailed(RuntimeError):
    def __init__(self, problems: list[str], daily: list[str]):
        super().__init__(" | ".join(problems))
        self.problems, self.daily = problems, daily


def has_key() -> bool:
    return bool(os.environ.get("CEREBRAS_API_KEY", "").strip())


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.environ['CEREBRAS_API_KEY'].strip()}", "Content-Type": "application/json"}


def available() -> list[str] | None:
    """Model ids this key can use (cached for an hour); None if they can't be listed."""
    if _CACHE["ids"] is not None and time.time() - _CACHE["at"] < 3600:
        return _CACHE["ids"]
    try:
        r = httpx.get(f"{BASE}/models", headers=_headers(), timeout=20)
        r.raise_for_status()
        ids = [m["id"] for m in r.json().get("data", []) if not any(x in m["id"].lower() for x in _SKIP)]
    except Exception:  # noqa: BLE001
        return None
    _CACHE.update(at=time.time(), ids=ids)
    return ids


def models() -> list[str]:
    avail = available()
    if not avail:
        return PREFERRED[:MAX_MODELS]
    chain = [m for m in PREFERRED if m in avail] + sorted(m for m in avail if m not in PREFERRED)
    return chain[:MAX_MODELS]


def test_key() -> tuple[bool, str]:
    try:
        r = httpx.get(f"{BASE}/models", headers=_headers(), timeout=20)
        if r.status_code in (401, 403):
            return False, "Cerebras rejected the key. Copy it again from cloud.cerebras.ai → API Keys."
        r.raise_for_status()
        ids = [m["id"] for m in r.json().get("data", [])]
        return True, f"Cerebras key works ✅ ({len(ids)} models: {', '.join(ids[:6])})"
    except Exception as e:  # noqa: BLE001
        return False, f"Cerebras could not be reached: {type(e).__name__}: {str(e)[:200]}"


def _msg(r: httpx.Response) -> str:
    try:
        j = r.json()
        m = j.get("message") or (j.get("error") or {}).get("message") if isinstance(j, dict) else None
        m = m or r.text
    except ValueError:
        m = r.text
    return " ".join(str(m).split())[:260]


def _wait_secs(r: httpx.Response) -> float:
    for h in ("retry-after", "x-ratelimit-reset-tokens-minute", "x-ratelimit-reset-requests-minute"):
        try:
            v = float(r.headers.get(h) or 0)
            if v:
                return v
        except ValueError:
            pass
    return 0.0


def _daily(r: httpx.Response, msg: str) -> str | None:
    """If the daily allowance is used up, how long until it frees up (text); otherwise None."""
    day_left = r.headers.get("x-ratelimit-remaining-tokens-day") or r.headers.get("x-ratelimit-remaining-requests-day")
    if "day" in msg.lower() or "daily" in msg.lower() or (day_left is not None and str(day_left).strip() in ("0", "0.0")):
        for h in ("x-ratelimit-reset-tokens-day", "x-ratelimit-reset-requests-day", "retry-after"):
            try:
                secs = float(r.headers.get(h) or 0)
            except ValueError:
                secs = 0
            if secs:
                mins = int(secs // 60) + 1
                return f"{mins // 60} h {mins % 60} min" if mins >= 60 else f"{mins} min"
        return ""
    return None


def chat(system: str, user: str, json_mode: bool, lite: tuple[str, str] | None = None, max_out: int = 8000,
         effort: str = "medium", on_wait=None) -> str:
    """Same behaviour as the Groq helper: per model, full request, then the lighter one if too long; wait once
    on a per-minute limit; then the next model. Raises CerebrasFailed with the reason for every model."""
    problems, daily = [], []
    for model in models():
        attempts = [("full", system, user, max_out)] + ([("lighter", lite[0], lite[1], min(max_out, 4500))] if lite else [])
        i, waited, json_retry, use_effort = 0, False, False, "gpt-oss" in model
        while i < len(attempts):
            label, sys_msg, user_msg, out = attempts[i]
            body = {"model": model, "temperature": 0.2, "max_completion_tokens": out,
                    "messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}]}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            if use_effort:
                body["reasoning_effort"] = "low" if label == "lighter" else effort
            try:
                r = httpx.post(f"{BASE}/chat/completions", headers=_headers(), json=body, timeout=180)
            except httpx.HTTPError as e:
                problems.append(f"cerebras {model}: connection problem ({type(e).__name__})")
                break
            if r.status_code == 200:
                return (r.json()["choices"][0]["message"].get("content") or "")
            msg = _msg(r)
            low = msg.lower()
            if r.status_code in (401, 403):
                raise CerebrasFailed([f"cerebras: key rejected ({msg})"], [])
            if r.status_code == 429:
                d = _daily(r, msg)
                if d is not None:
                    problems.append(f"cerebras {model}: daily limit reached ({msg})")
                    daily.append(d)
                    break
                wait = _wait_secs(r)
                if not waited and 0 < wait <= 65:
                    waited = True
                    if on_wait:
                        on_wait(f"cerebras {model}", wait)
                    time.sleep(wait + 1)
                    continue
                problems.append(f"cerebras {model}: limit reached ({msg})")
                break
            if r.status_code == 400 and "reasoning" in low and use_effort:
                use_effort = False          # this model doesn't take reasoning_effort
                continue
            if r.status_code == 400 and "json" in low and not json_retry:
                json_retry = True
                continue
            if r.status_code == 413 or (r.status_code == 400 and re.search(r"context|too long|too large|maximum|length", low)):
                if i + 1 < len(attempts):
                    i += 1
                    continue
                problems.append(f"cerebras {model}: too long ({msg})")
                break
            problems.append(f"cerebras {model}: {msg or r.status_code}")
            break
    raise CerebrasFailed(problems or ["cerebras: no model available"], daily)
