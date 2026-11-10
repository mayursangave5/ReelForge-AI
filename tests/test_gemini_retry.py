from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reels.script.llm import (
    GeminiLLM,
    LLMError,
    ModelAccessError,
    QuotaExhausted,
    calculate_backoff,
    is_temporary_error,
    mask_key,
    sanitize_message,
)


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


class DummyGeminiError(Exception):
    def __init__(self, message: str, code: int | None = None, status: str | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


class GeminiRetryTests(unittest.TestCase):
    def test_mask_key_protects_secrets(self):
        self.assertEqual(mask_key("sample-test-gemini-api-key-xyz1234"), "...1234")
        self.assertEqual(mask_key("short"), "***")
        self.assertEqual(mask_key(None), "<none>")

    def test_sanitize_message_scrubs_secrets(self):
        key = "test-secret-gemini-key-9999"
        msg = f"Error communicating with Gemini using key {key} on endpoint"
        sanitized = sanitize_message(msg, [key])
        self.assertNotIn(key, sanitized)
        self.assertIn("...9999", sanitized)

    def test_is_temporary_error_detects_503_429_500(self):
        err_503 = DummyGeminiError("503 UNAVAILABLE — This model is currently experiencing high demand.", code=503, status="UNAVAILABLE")
        is_temp, code, status = is_temporary_error(err_503)
        self.assertTrue(is_temp)
        self.assertEqual(code, 503)

        err_429 = DummyGeminiError("Resource exhausted: rate limit exceeded", code=429, status="RESOURCE_EXHAUSTED")
        is_temp, code, status = is_temporary_error(err_429)
        self.assertTrue(is_temp)
        self.assertEqual(code, 429)

        err_500 = DummyGeminiError("Internal server error", code=500)
        is_temp, code, status = is_temporary_error(err_500)
        self.assertTrue(is_temp)

        # Permanent error
        err_400 = DummyGeminiError("Invalid argument", code=400)
        is_temp, code, status = is_temporary_error(err_400)
        self.assertFalse(is_temp)

    def test_calculate_backoff_increases_exponentially_with_jitter(self):
        d1 = calculate_backoff(1, base_delay=1.0, max_delay=30.0)
        d2 = calculate_backoff(2, base_delay=1.0, max_delay=30.0)
        d3 = calculate_backoff(3, base_delay=1.0, max_delay=30.0)
        self.assertGreater(d2, d1)
        self.assertGreater(d3, d2)
        d_large = calculate_backoff(10, base_delay=1.0, max_delay=10.0)
        self.assertLessEqual(d_large, 15.0)  # max_delay + jitter

    @patch("time.sleep", return_value=None)
    def test_503_retries_and_succeeds(self, mock_sleep):
        mock_client = MagicMock()
        # Fail twice with 503, then succeed on 3rd attempt
        mock_client.models.generate_content.side_effect = [
            DummyGeminiError("503 UNAVAILABLE: high demand", code=503, status="UNAVAILABLE"),
            DummyGeminiError("503 UNAVAILABLE: high demand", code=503, status="UNAVAILABLE"),
            FakeResponse('{"title": "retry_success"}'),
        ]

        llm = GeminiLLM(
            api_key="test-key-12345678",
            model="gemini-3.6-flash",
            max_retries=5,
            base_delay=0.01,
            client_factory=lambda k: mock_client,
        )

        res = llm.generate_json("system", "prompt")
        self.assertEqual(res, {"title": "retry_success"})
        self.assertEqual(mock_client.models.generate_content.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep", return_value=None)
    def test_multi_key_rotation(self, mock_sleep):
        key1 = "test-key-AAAA1111"
        key2 = "test-key-BBBB2222"

        client1 = MagicMock()
        client2 = MagicMock()

        # Key 1 fails with 503, Key 2 succeeds
        client1.models.generate_content.side_effect = DummyGeminiError("503 UNAVAILABLE", code=503, status="UNAVAILABLE")
        client2.models.generate_content.return_value = FakeResponse('{"status": "key2_success"}')

        clients = {key1: client1, key2: client2}

        llm = GeminiLLM(
            api_keys=[key1, key2],
            model="gemini-3.6-flash",
            max_retries=5,
            base_delay=0.01,
            client_factory=lambda k: clients[k],
        )

        res = llm.generate_json("system", "prompt")
        self.assertEqual(res, {"status": "key2_success"})
        self.assertEqual(client1.models.generate_content.call_count, 1)
        self.assertEqual(client2.models.generate_content.call_count, 1)

    @patch("time.sleep", return_value=None)
    def test_fallback_model_when_primary_exhausts_retries(self, mock_sleep):
        mock_client = MagicMock()

        def side_effect(model, contents, config):
            if model == "gemini-3.6-flash":
                raise DummyGeminiError("503 UNAVAILABLE: high demand", code=503, status="UNAVAILABLE")
            elif model == "gemini-2.5-flash":
                return FakeResponse('{"status": "fallback_success"}')
            raise ValueError(f"Unknown model: {model}")

        mock_client.models.generate_content.side_effect = side_effect

        llm = GeminiLLM(
            api_key="test-key-12345678",
            model="gemini-3.6-flash",
            fallback_model="gemini-2.5-flash",
            max_retries=3,
            base_delay=0.01,
            client_factory=lambda k: mock_client,
        )

        res = llm.generate_json("system", "prompt")
        self.assertEqual(res, {"status": "fallback_success"})
        # 3 calls for primary + 1 call for fallback = 4 calls total
        self.assertEqual(mock_client.models.generate_content.call_count, 4)

    def test_non_retryable_error_fails_immediately(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = DummyGeminiError("400 Bad Request: invalid content", code=400)

        llm = GeminiLLM(
            api_key="test-key-12345678",
            model="gemini-3.6-flash",
            max_retries=5,
            client_factory=lambda k: mock_client,
        )

        with self.assertRaises(DummyGeminiError):
            llm.generate_json("system", "prompt")
        # Fails immediately without retrying
        self.assertEqual(mock_client.models.generate_content.call_count, 1)

    @patch("time.sleep", return_value=None)
    def test_all_retries_and_models_exhausted_raises(self, mock_sleep):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = DummyGeminiError("503 UNAVAILABLE", code=503, status="UNAVAILABLE")

        llm = GeminiLLM(
            api_key="test-key-12345678",
            model="gemini-3.6-flash",
            fallback_model="gemini-2.5-flash",
            max_retries=2,
            base_delay=0.01,
            client_factory=lambda k: mock_client,
        )

        with self.assertRaises(LLMError) as ctx:
            llm.generate_json("system", "prompt")
        self.assertIn("failed after 2 attempts", str(ctx.exception))
        # 2 attempts on primary + 2 attempts on fallback = 4 calls
        self.assertEqual(mock_client.models.generate_content.call_count, 4)

    @patch("time.sleep", return_value=None)
    def test_quota_exhaustion_raises_quota_exhausted(self, mock_sleep):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = DummyGeminiError("429 RESOURCE_EXHAUSTED: quota exceeded", code=429, status="RESOURCE_EXHAUSTED")

        llm = GeminiLLM(
            api_key="test-key-12345678",
            model="gemini-3.6-flash",
            fallback_model="gemini-2.5-flash",
            max_retries=2,
            base_delay=0.01,
            client_factory=lambda k: mock_client,
        )

        with self.assertRaises(QuotaExhausted):
            llm.generate_json("system", "prompt")


if __name__ == "__main__":
    unittest.main()
