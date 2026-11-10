from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any, Protocol

from ..config import settings

logger = logging.getLogger("reels.script.llm")

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

# Source: https://ai.google.dev/gemini-api/docs/pricing (checked 2026-11-09).
# Only models whose Standard "Free Tier" column says "Free of charge".
FREE_TIER_MODELS = frozenset(
    {
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    }
)

TEMPORARY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
TEMPORARY_KEYWORDS = (
    "unavailable",
    "high demand",
    "resource_exhausted",
    "rate limit",
    "rate_limit",
    "quota",
    "deadline exceeded",
    "overloaded",
    "try again",
    "503",
    "429",
    "500",
    "502",
    "504",
    "connection reset",
    "remote disconnected",
    "connection refused",
    "server error",
    "forcibly closed",
    "10054",
    "readerror",
    "connecterror",
    "timed out",
    "timeout",
    "broken pipe",
    "closed by the remote host",
)


def mask_key(key: str | None) -> str:
    """Safely mask API key for logging without exposing secrets."""
    if not key:
        return "<none>"
    s = str(key).strip()
    if len(s) <= 8:
        return "***"
    return f"...{s[-4:]}"


def sanitize_message(msg: str, secrets: list[str]) -> str:
    """Scrub raw API keys from exception messages and error text."""
    sanitized = str(msg)
    for secret in secrets:
        if secret and len(secret) > 4:
            sanitized = sanitized.replace(secret, mask_key(secret))
    return sanitized


def is_temporary_error(exc: Exception) -> tuple[bool, int | None, str]:
    """Determine whether an error is transient (e.g. 503 high demand, 429 rate limit)."""
    code = getattr(exc, "code", None)
    if code is None:
        code = getattr(exc, "status_code", None)
    status = str(getattr(exc, "status", "")).upper()
    msg = str(exc).lower()

    if code is not None:
        try:
            int_code = int(code)
            if int_code in TEMPORARY_STATUS_CODES:
                return True, int_code, status or f"HTTP {int_code}"
            if int_code in (400, 401, 403, 404):
                if not any(k in msg for k in ("resource_exhausted", "high demand", "rate limit")):
                    return False, int_code, status or f"HTTP {int_code}"
        except (ValueError, TypeError):
            pass

    if any(k in status.lower() for k in ("unavailable", "resource_exhausted", "deadline_exceeded")):
        return True, code, status

    if any(k in msg for k in TEMPORARY_KEYWORDS):
        return True, code, status or "TEMPORARY_ERROR"

    return False, code, status or "ERROR"


def calculate_backoff(attempt: int, base_delay: float = 1.5, max_delay: float = 30.0) -> float:
    """Calculate exponential backoff with random jitter."""
    exp = base_delay * (2 ** max(0, attempt - 1))
    delay = min(max_delay, exp)
    jitter = random.uniform(0.1, max(0.2, 0.4 * delay))
    return delay + jitter


class LLMError(RuntimeError):
    pass


class QuotaExhausted(LLMError):
    """Free-tier quota hit. Stop; never switch to a paid model."""


class ModelAccessError(LLMError):
    pass


def ensure_free_tier(model: str) -> None:
    if model not in FREE_TIER_MODELS:
        raise LLMError(
            f"Model '{model}' is not on the free-tier allowlist; refusing to run "
            "to protect the zero-cost budget. Allowed models: "
            + ", ".join(sorted(FREE_TIER_MODELS))
        )


class LLM(Protocol):
    name: str
    is_mock: bool

    def generate_json(self, system: str, prompt: str) -> dict: ...


def parse_json(text: str) -> dict:
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("response did not contain a JSON object")
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"invalid JSON from model: {exc}") from exc


class GeminiLLM:
    name = "gemini"
    is_mock = False

    def __init__(
        self,
        api_key: str | list[str] | None = None,
        model: str | None = None,
        fallback_model: str | None = None,
        max_retries: int | None = None,
        base_delay: float | None = None,
        max_delay: float | None = None,
        api_keys: list[str] | None = None,
        client_factory=None,
    ) -> None:
        raw_keys: list[str] = []
        if api_keys:
            raw_keys.extend(api_keys)
        if api_key:
            if isinstance(api_key, list):
                raw_keys.extend(api_key)
            elif isinstance(api_key, str) and api_key.strip():
                raw_keys.append(api_key.strip())
        if not raw_keys:
            raw_keys.extend(settings.gemini_api_keys)

        self._api_keys = [k.strip() for k in raw_keys if k and k.strip()]
        if not self._api_keys:
            raise LLMError(
                "No Gemini key configured. Add a free-tier GEMINI_API_KEY to .env, or run with --mock."
            )

        # De-duplicate while preserving order
        seen = set()
        deduped = []
        for k in self._api_keys:
            if k not in seen:
                seen.add(k)
                deduped.append(k)
        self._api_keys = deduped

        self._primary_model = model or settings.gemini_model
        self._fallback_model = (
            fallback_model
            if fallback_model is not None
            else settings.gemini_fallback_model
        )

        ensure_free_tier(self._primary_model)
        if self._fallback_model and self._fallback_model != self._primary_model:
            ensure_free_tier(self._fallback_model)

        self._models = [self._primary_model]
        if self._fallback_model and self._fallback_model != self._primary_model:
            self._models.append(self._fallback_model)

        self.active_model = self._primary_model
        self.max_retries = max_retries if max_retries is not None else settings.gemini_max_retries
        self.base_delay = base_delay if base_delay is not None else settings.gemini_base_delay
        self.max_delay = max_delay if max_delay is not None else settings.gemini_max_delay
        self._client_factory = client_factory
        self._clients: dict[str, Any] = {}

    def _get_client(self, api_key: str):
        if api_key not in self._clients:
            if self._client_factory:
                self._clients[api_key] = self._client_factory(api_key)
            else:
                from google import genai
                from google.genai import types

                self._clients[api_key] = genai.Client(
                    api_key=api_key,
                    http_options=types.HttpOptions(
                        timeout=120000,
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                )
        return self._clients[api_key]

    def _key_label(self, api_key: str) -> str:
        try:
            idx = self._api_keys.index(api_key) + 1
        except ValueError:
            idx = "?"
        return f"Key {idx} ({mask_key(api_key)})"

    def generate_json(self, system: str, prompt: str) -> dict:
        from google.genai import types

        last_exc: Exception | None = None
        last_error_was_quota = False

        for model_idx, model in enumerate(self._models):
            self.active_model = model
            is_fallback = model_idx > 0
            if is_fallback:
                logger.warning(
                    "Primary model '%s' was unavailable. Automatically falling back to '%s'.",
                    self._primary_model,
                    model,
                )

            key_idx = 0
            for attempt in range(1, self.max_retries + 1):
                current_key = self._api_keys[key_idx % len(self._api_keys)]
                key_label = self._key_label(current_key)
                client = self._get_client(current_key)

                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system,
                            response_mime_type="application/json",
                            temperature=0.7,
                        ),
                    )
                    return parse_json(response.text or "")

                except Exception as exc:
                    last_exc = exc
                    sanitized_msg = sanitize_message(str(exc), self._api_keys)
                    code = getattr(exc, "code", None)
                    msg_lower = sanitized_msg.lower()

                    # Fatal authentication error
                    if code in (401, 403) or "permission_denied" in msg_lower or "api_key_invalid" in msg_lower:
                        logger.warning(
                            "Gemini rejected %s (HTTP %s): %s.",
                            key_label,
                            code,
                            sanitized_msg,
                        )
                        if len(self._api_keys) > 1 and attempt < self.max_retries:
                            key_idx += 1
                            continue
                        raise ModelAccessError(
                            f"Gemini rejected key or model ({sanitized_msg}). Use a valid free-tier key."
                        ) from exc

                    is_temp, status_code, status_label = is_temporary_error(exc)
                    if is_temp:
                        if status_code == 429 or "resource_exhausted" in msg_lower or "quota" in msg_lower:
                            last_error_was_quota = True

                        if attempt < self.max_retries:
                            delay = calculate_backoff(attempt, self.base_delay, self.max_delay)
                            next_key = self._api_keys[(key_idx + 1) % len(self._api_keys)]
                            next_label = self._key_label(next_key)
                            rotate_info = f" Rotating to {next_label}." if len(self._api_keys) > 1 else ""

                            logger.warning(
                                "Gemini API temporary error [%s] on model '%s' using %s: %s. "
                                "Retrying in %.2fs (attempt %d/%d).%s",
                                status_label,
                                model,
                                key_label,
                                sanitized_msg,
                                delay,
                                attempt,
                                self.max_retries,
                                rotate_info,
                            )
                            time.sleep(delay)
                            key_idx += 1
                            continue
                        else:
                            logger.warning(
                                "Gemini model '%s' exhausted all %d retry attempts using %d key(s). Last error [%s]: %s",
                                model,
                                self.max_retries,
                                len(self._api_keys),
                                status_label,
                                sanitized_msg,
                            )
                            break
                    else:
                        logger.error(
                            "Gemini non-retryable error on model '%s' using %s: %s",
                            model,
                            key_label,
                            sanitized_msg,
                        )
                        raise

        clean_final = sanitize_message(str(last_exc), self._api_keys)
        if last_error_was_quota:
            raise QuotaExhausted(
                f"Gemini free-tier quota/rate limit exhausted across all models and keys ({clean_final}). "
                "Check AI Studio limits and retry later."
            ) from last_exc

        raise LLMError(
            f"Gemini generation failed after {self.max_retries} attempts across models "
            f"{self._models}: {clean_final}"
        ) from last_exc


class MockLLM:
    """Deterministic provider for offline tests. Returns canned Hindi JSON."""

    name = "mock"
    is_mock = True

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, system: str, prompt: str) -> dict:
        self.calls += 1
        if '"supported"' in prompt:
            claims = re.findall(r"^- (.+)$", prompt, flags=re.MULTILINE)
            return {
                "results": [
                    {"claim_hi": claim, "supported": True, "reason_hi": "स्रोत में मौजूद"}
                    for claim in claims
                ]
            }
        if '"instagram"' in prompt:
            return {
                "instagram": {
                    "caption": "अंतरिक्ष में बढ़ता कचरा एक बड़ी चुनौती है 🚀 जानिए भारत इसे कैसे साफ करेगा।",
                    "hashtags": ["हिंदी", "space", "india", "reels", "facts", "science", "shorts", "knowledge", "viral", "trending"],
                },
                "youtube": {
                    "title": "अंतरिक्ष का कचरा साफ करेगा भारत, जानिए कैसे",
                    "caption": "भारत की पहली स्पेस डेब्रिस सफाई सुविधा और भविष्य की योजनाओं की पूरी जानकारी हिंदी में। वीडियो पसंद आए तो लाइक और शेयर करें।",
                    "hashtags": ["Shorts", "हिंदी", "space", "india", "science"],
                    "tags": ["हिंदी Facts", "space news", "india space", "science in hindi", "अंतरिक्ष"],
                },
            }
        return {
            "title_hi": "अंतरिक्ष में बढ़ता कचरा",
            "hook_hi": "अंतरिक्ष में चक्कर लगा रहा है खतरनाक कचरा, जानिए कैसे।",
            "scenes": [
                {
                    "narration_hi": "पृथ्वी के चारों ओर अंतरिक्ष में लाखों छोटे-बड़े टुकड़े लगातार चक्कर लगा रहे हैं, जिन्हें अंतरिक्ष कचरा कहा जाता है।",
                    "visual_en": "cinematic view of Earth orbit with debris, vertical 9:16, no text",
                    "text_hi": "अंतरिक्ष में कचरा",
                    "duration_s": 7,
                },
                {
                    "narration_hi": "ये टुकड़े हजारों किलोमीटर प्रति घंटे की रफ्तार से चलते हैं और उपग्रहों तथा अंतरिक्ष यात्रियों के लिए बड़ा खतरा बन सकते हैं।",
                    "visual_en": "satellite dodging a fast moving metal fragment, vertical 9:16, no text",
                    "text_hi": "बड़ा खतरा",
                    "duration_s": 8,
                },
                {
                    "narration_hi": "भारत अब इस कचरे को साफ करने के लिए नई तकनीक और रोबोटिक सिस्टम पर काम कर रहा है, जो भविष्य की अंतरिक्ष यात्राओं को सुरक्षित बनाएगा।",
                    "visual_en": "futuristic Indian space robot collecting debris, vertical 9:16, no text",
                    "text_hi": "भारत की तकनीक",
                    "duration_s": 8,
                },
                {
                    "narration_hi": "साफ और सुरक्षित अंतरिक्ष हमारी अगली पीढ़ी के लिए बहुत जरूरी है, इसलिए यह मिशन सबके लिए महत्वपूर्ण है।",
                    "visual_en": "clean Earth orbit at sunrise, cinematic, vertical 9:16, no text",
                    "text_hi": "साफ अंतरिक्ष",
                    "duration_s": 7,
                },
            ],
            "cta_hi": "ऐसी रोचक जानकारी के लिए फॉलो करना न भूलें।",
            "estimated_duration_s": 30,
            "claims": [
                {
                    "claim_hi": "पृथ्वी के चारों ओर अंतरिक्ष कचरा मौजूद है।",
                    "sources": ["https://example.com/source"],
                    "confidence": "high",
                }
            ],
        }


def get_llm(force_mock: bool = False) -> LLM:
    if force_mock:
        return MockLLM()
    keys = settings.gemini_api_keys
    if keys:
        return GeminiLLM(
            api_keys=keys,
            model=settings.gemini_model,
            fallback_model=settings.gemini_fallback_model,
            max_retries=settings.gemini_max_retries,
            base_delay=settings.gemini_base_delay,
            max_delay=settings.gemini_max_delay,
        )
    raise LLMError(
        "No Gemini key configured. Add a free-tier GEMINI_API_KEY to .env, or run with --mock."
    )
