"""Tests for ASR service, Groq engine, Local engine, and failover behavior.

Network-independent unit tests using mocks.
Includes skipped-by-default integration tests for optional live verification.
"""

from __future__ import annotations

import io
import os
from unittest.mock import MagicMock, patch
import wave
import httpx
import numpy as np
import pytest

from app.asr.bias import build_bias_prompt
from app.asr.groq_whisper import GroqASRError, GroqWhisperEngine
from app.asr.local_whisper import LocalWhisperEngine
from app.asr.service import ASRService
from app.config import Settings
from app.ingest.audio import IngestedAudio


def _make_dummy_audio(duration_s: float = 1.0) -> IngestedAudio:
    """Create a dummy IngestedAudio instance."""
    num_samples = int(duration_s * 16000)
    samples = np.zeros(num_samples, dtype=np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(samples.tobytes())
    return IngestedAudio(
        wav_bytes=buf.getvalue(),
        duration_ms=int(duration_s * 1000),
        clip_ratio=0.0,
        pcm_samples=samples,
    )


# ==================== GroqWhisperEngine Unit Tests ====================


def test_groq_whisper_engine_missing_key_fails_fast() -> None:
    """Initializing GroqWhisperEngine with empty key raises ValueError immediately."""
    with pytest.raises(ValueError, match="GROQ_API_KEY is required"):
        GroqWhisperEngine(api_key="")

    with pytest.raises(ValueError, match="GROQ_API_KEY is required"):
        GroqWhisperEngine(api_key="   ")


def test_groq_whisper_engine_successful_call() -> None:
    """Groq engine parses verbose_json and enforces task='transcribe' and language='ur'."""
    secret_key = "gsk_test_secret_key_12345"
    audio = _make_dummy_audio(1.0)

    mock_resp = {
        "text": "احمد بھائی دو کلو چینی",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "text": "احمد بھائی دو کلو چینی",
                "avg_logprob": -0.25,
                "no_speech_prob": 0.05,
            }
        ],
    }

    def custom_handler(request: httpx.Request) -> httpx.Response:
        # Assert auth header is present
        assert request.headers["Authorization"] == f"Bearer {secret_key}"
        # Assert multipart content was sent
        content = request.content.decode("latin1", errors="ignore")
        assert "whisper-large-v3" in content
        assert "transcribe" in content  # AGENTS.md rule 4: NEVER translate
        assert "ur" in content
        return httpx.Response(200, json=mock_resp)

    transport = httpx.MockTransport(custom_handler)
    with httpx.Client(transport=transport) as mock_client:
        engine = GroqWhisperEngine(api_key=secret_key, client=mock_client)
        payload = engine.transcribe(
            audio=audio,
            job_id="job_001",
            shop_id="shop_001",
            prompt="ایک دو چینی",
        )

    assert payload.engine == "groq_whisper"
    assert payload.model_name == "whisper-large-v3"
    assert payload.language == "ur"
    assert payload.raw_text == "احمد بھائی دو کلو چینی"
    assert len(payload.segments) == 1
    assert payload.segments[0].avg_logprob == -0.25
    assert payload.failover_reason is None
    assert payload.asr_confidence > 0.7


@pytest.mark.parametrize(
    "status_code, expected_reason",
    [
        (401, "auth_failure"),
        (429, "rate_limit"),
        (500, "server_error"),
        (503, "server_error"),
    ],
)
def test_groq_whisper_engine_http_errors_never_leak_key(
    status_code: int, expected_reason: str
) -> None:
    """HTTP errors are categorized and NEVER leak the API key in exceptions."""
    secret_key = "gsk_super_secret_never_leak_me"
    audio = _make_dummy_audio(1.0)

    transport = httpx.MockTransport(lambda req: httpx.Response(status_code, text="Error body"))
    with httpx.Client(transport=transport) as mock_client:
        engine = GroqWhisperEngine(api_key=secret_key, client=mock_client)
        with pytest.raises(GroqASRError) as exc_info:
            engine.transcribe(audio=audio, job_id="job_001", shop_id="shop_001")

    assert exc_info.value.reason_category == expected_reason
    # Verify API key is NOT in error string or representation
    assert secret_key not in str(exc_info.value)
    assert secret_key not in repr(exc_info.value)


def test_groq_whisper_engine_timeout_and_network_errors() -> None:
    """Timeouts and connection failures are categorized and never leak key."""
    secret_key = "gsk_super_secret_never_leak_me"
    audio = _make_dummy_audio(1.0)

    def timeout_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out")

    transport = httpx.MockTransport(timeout_handler)
    with httpx.Client(transport=transport) as mock_client:
        engine = GroqWhisperEngine(api_key=secret_key, client=mock_client)
        with pytest.raises(GroqASRError) as exc_info:
            engine.transcribe(audio=audio, job_id="job_001", shop_id="shop_001")
    assert exc_info.value.reason_category == "timeout"
    assert secret_key not in str(exc_info.value)


# ==================== LocalWhisperEngine Unit Tests ====================


def test_local_whisper_engine_mocked() -> None:
    """Local engine enforces condition_on_previous_text=False and language='ur'."""
    audio = _make_dummy_audio(1.0)

    mock_segment = MagicMock()
    mock_segment.text = "دو کلو چینی"
    mock_segment.start = 0.0
    mock_segment.end = 1.0
    mock_segment.avg_logprob = -0.3
    mock_segment.no_speech_prob = 0.05

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())

    engine = LocalWhisperEngine(model_instance=mock_model)
    payload = engine.transcribe(
        audio=audio,
        job_id="job_local_01",
        shop_id="shop_001",
        prompt="چینی",
    )

    # Check that model.transcribe was called with hard rules
    mock_model.transcribe.assert_called_once()
    _, kwargs = mock_model.transcribe.call_args
    assert kwargs["language"] == "ur"
    assert kwargs["task"] == "transcribe"  # AGENTS.md rule 4
    assert kwargs["condition_on_previous_text"] is False  # AGENTS.md rule 5
    assert kwargs["temperature"] == 0.0

    assert payload.engine == "local_faster_whisper"
    assert payload.model_name == "small-int8"
    assert payload.raw_text == "دو کلو چینی"
    assert payload.failover_reason is None


# ==================== ASRService & Failover Tests ====================


def test_asr_service_missing_key_fail_fast() -> None:
    """ASRService with ASR_ENGINE='groq' and missing GROQ_API_KEY fails fast at startup."""
    bad_settings = Settings(ASR_ENGINE="groq", GROQ_API_KEY="")
    with pytest.raises(ValueError, match="GROQ_API_KEY is missing or empty"):
        ASRService(settings=bad_settings)


def test_asr_service_automatic_failover(caplog: pytest.LogCaptureFixture) -> None:
    """When Groq fails with auth_failure/rate_limit, service logs WARNING and falls back to local."""
    secret_key = "gsk_test_mock_secret"
    settings = Settings(ASR_ENGINE="groq", GROQ_API_KEY=secret_key)
    audio = _make_dummy_audio(1.0)

    # Mock Groq to fail with auth_failure
    mock_groq = MagicMock()
    mock_groq.transcribe.side_effect = GroqASRError(
        "Invalid API Key", reason_category="auth_failure"
    )

    # Mock Local to succeed
    mock_local = MagicMock()
    mock_local_payload = MagicMock()
    mock_local_payload.engine = "local_faster_whisper"
    mock_local_payload.failover_reason = None
    mock_local.transcribe.return_value = mock_local_payload

    service = ASRService(
        settings=settings,
        groq_engine=mock_groq,
        local_engine=mock_local,
    )

    with caplog.at_level("WARNING"):
        payload = service.transcribe(
            audio=audio,
            job_id="job_failover",
            shop_id="shop_01",
        )

    # Assert Groq was attempted
    mock_groq.transcribe.assert_called_once()
    # Assert Local was called
    mock_local.transcribe.assert_called_once()

    # Assert payload records engine and failover_reason
    assert payload.engine == "local_faster_whisper"
    assert payload.failover_reason == "auth_failure"

    # Assert WARNING was logged with the category and NEVER the key
    assert any("auth_failure" in record.message for record in caplog.records)
    assert secret_key not in caplog.text


def test_asr_service_direct_local() -> None:
    """When ASR_ENGINE='local', Groq is not called at all."""
    settings = Settings(ASR_ENGINE="local", GROQ_API_KEY="")
    audio = _make_dummy_audio(1.0)

    mock_local = MagicMock()
    mock_local_payload = MagicMock()
    mock_local_payload.engine = "local_faster_whisper"
    mock_local_payload.failover_reason = None
    mock_local.transcribe.return_value = mock_local_payload

    service = ASRService(settings=settings, local_engine=mock_local)
    payload = service.transcribe(audio=audio, job_id="job_dir_local", shop_id="shop_01")

    mock_local.transcribe.assert_called_once()
    assert payload.failover_reason is None


# ==================== Live Integration Tests (Skipped Offline) ====================


@pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="Live Groq test requires GROQ_API_KEY in environment",
)
def test_live_groq_integration() -> None:  # pragma: no cover
    """Integration test hitting real Groq API when GROQ_API_KEY is available."""
    api_key = os.environ["GROQ_API_KEY"]
    engine = GroqWhisperEngine(api_key=api_key)
    audio = _make_dummy_audio(1.0)
    prompt = build_bias_prompt()
    payload = engine.transcribe(
        audio=audio,
        job_id="live_test_groq",
        shop_id="shop_demo",
        prompt=prompt,
    )
    assert payload.engine == "groq_whisper"
    assert payload.language == "ur"


@pytest.mark.skipif(
    not os.path.exists(os.path.expanduser("~/.cache/huggingface/hub/models--Systran--faster-whisper-small")),
    reason="Local Whisper model weights not present in local cache",
)
def test_live_local_whisper_integration() -> None:  # pragma: no cover
    """Integration test running real faster-whisper when weights are already cached."""
    engine = LocalWhisperEngine(model_size="small", device="cpu", compute_type="int8")
    audio = _make_dummy_audio(1.0)
    prompt = build_bias_prompt()
    payload = engine.transcribe(
        audio=audio,
        job_id="live_test_local",
        shop_id="shop_demo",
        prompt=prompt,
    )
    assert payload.engine == "local_faster_whisper"
    assert payload.language == "ur"
