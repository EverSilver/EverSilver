"""Audio endpoints + history truncation for small local models."""
from __future__ import annotations
import io


def test_transcription_returns_503_when_no_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    fake = io.BytesIO(b"RIFFfakewav")
    r = client.post(
        "/openai/v1/audio/transcriptions",
        files={"file": ("clip.wav", fake, "audio/wav")},
        data={"model": "whisper-1"},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["error"]["type"] == "configuration_error"
    assert "OPENAI_API_KEY" in body["error"]["message"]


def test_transcription_calls_litellm_when_key_present(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    captured: dict = {}

    class _R:
        def model_dump(self):
            return {"text": "hello world"}

    def fake_transcription(**kw):
        captured.update(kw)
        return _R()

    import litellm

    monkeypatch.setattr(litellm, "transcription", fake_transcription)
    fake = io.BytesIO(b"RIFFfakewav")
    r = client.post(
        "/openai/v1/audio/transcriptions",
        files={"file": ("clip.wav", fake, "audio/wav")},
        data={"model": "whisper-1", "language": "en"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "hello world"
    assert captured["model"] == "whisper-1"
    assert captured["language"] == "en"
    assert captured["api_key"] == "sk-test"


def test_transcription_normalizes_whisper_v1_alias(client, monkeypatch):
    """Eversilver historically sends `whisper-v1`; LiteLLM doesn't know
    that name. The endpoint must map it to OpenAI's real `whisper-1`."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    captured: dict = {}

    class _R:
        def model_dump(self):
            return {"text": "ok"}

    def fake_transcription(**kw):
        captured.update(kw)
        return _R()

    import litellm

    monkeypatch.setattr(litellm, "transcription", fake_transcription)
    r = client.post(
        "/openai/v1/audio/transcriptions",
        files={"file": ("clip.webm", io.BytesIO(b"data"), "audio/webm")},
        data={"model": "whisper-v1"},
    )
    assert r.status_code == 200, r.text
    assert captured["model"] == "whisper-1"  # normalized
    assert captured["api_key"] == "sk-test"
    # api_base must be forced to OpenAI's host so OPENAI_BASE_URL
    # (set globally to e.g. a proxy) can't redirect Whisper to a host
    # that has no /audio/transcriptions route.
    assert captured["api_base"] == "https://api.openai.com/v1"


def test_speech_returns_503_when_no_openai_key(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post(
        "/openai/v1/audio/speech",
        json={"input": "hello", "voice": "alloy"},
    )
    assert r.status_code == 503
    assert r.json()["error"]["type"] == "configuration_error"


def test_speech_returns_audio_when_key_present(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class _Audio:
        content = b"\xff\xfbfake-mp3-bytes"

    import litellm

    monkeypatch.setattr(litellm, "speech", lambda **kw: _Audio())
    r = client.post(
        "/openai/v1/audio/speech",
        json={"input": "hello", "voice": "alloy"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/")
    assert r.content == b"\xff\xfbfake-mp3-bytes"


def test_history_truncation_for_small_models():
    """Small models get a capped transcript; large models pass through."""
    from app.litellm_client import _truncate_history_for_small_models

    sys = [{"role": "system", "content": "be helpful"}]
    user_asst = [
        {"role": "user", "content": f"u{i}"} if i % 2 == 0 else {"role": "assistant", "content": f"a{i}"}
        for i in range(20)
    ]
    msgs = sys + user_asst

    # gemma3:1b is small -> truncated to system + last 6
    out = _truncate_history_for_small_models("ollama_chat/gemma3:1b-it-qat", msgs)
    assert out[0]["role"] == "system"
    assert len(out) == 1 + 6
    assert out[-1]["content"] == "a19"

    # gpt-4o-mini is large -> passes through
    out = _truncate_history_for_small_models("openai/gpt-4o-mini", msgs)
    assert out == msgs


def test_history_truncation_no_op_for_short_threads():
    from app.litellm_client import _truncate_history_for_small_models

    msgs = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
        {"role": "assistant", "content": "a"},
    ]
    assert _truncate_history_for_small_models("ollama_chat/gemma3:1b-it-qat", msgs) == msgs
