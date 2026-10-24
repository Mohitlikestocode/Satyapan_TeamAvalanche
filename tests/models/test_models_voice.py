"""Voice notes: safe decoding, the transcript-first page, the signed voice band, and verdicts from the words plus the voice sign.

Model calls are replaced only where a model cannot run in CI; decoding uses real ffmpeg when it is installed.
"""
import io
import math
import struct
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from satyapan.api.app import app
from satyapan.api.ext import models_voice as page
from satyapan.contracts.models import Strength, Tier
from satyapan.layers.l2_forensics import audio
from satyapan.plugins import models_voice

SCAM_HI = "नमस्ते, गारंटीड 30% मुनाफ़ा हर महीने। अभी 25000 रुपये alpha.gain88@ybl पर भेजिए।"
SCAM_EN = "Guaranteed 30% profit every month, zero risk. Pay Rs 25000 to alpha.gain88@ybl now to join."


def wav_bytes(samples: np.ndarray, sr: int = 16000) -> bytes:
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))
    return b.getvalue()


def tone(seconds: float = 2.0, sr: int = 16000) -> np.ndarray:
    return np.array([0.3 * math.sin(2 * math.pi * 220 * i / sr) for i in range(int(seconds * sr))], dtype=np.float32)


needs_ffmpeg = pytest.mark.skipif(audio.ffmpeg_path() is None, reason="ffmpeg not installed")


@needs_ffmpeg
def test_decode_reads_a_tone_and_rejects_silence_garbage_and_too_short():
    wav = audio.decode(wav_bytes(tone(2.0, 44100), 44100))
    assert wav is not None and abs(len(wav) - 32000) < 400 and wav.dtype == np.float32   # resampled to 16 kHz mono
    assert audio.decode(wav_bytes(np.zeros(32000, dtype=np.float32))) is None            # silence
    assert audio.decode(b"definitely not audio") is None
    assert audio.decode(wav_bytes(tone(0.3))) is None                                     # under the minimum length
    assert audio.decode(b"x" * (audio.MAX_BYTES + 1)) is None


@needs_ffmpeg
def test_reencoding_like_a_chat_app_round_trips():
    w = tone(2.0)
    for codec in ("opus24k", "aac64k", "tel8k"):
        enc = audio.encode(w, codec)
        assert enc and audio.decode(enc) is not None


def test_two_detectors_that_disagree_say_nothing_about_the_voice():
    cal = {"primary": {"threshold": 0.0, "strong_threshold": -3.0}, "second": {"threshold": 0.0}}
    assert audio.judge(audio.VoiceScore(primary=-1.0, second=-1.0), cal) == ("fake", Strength.WEAK_SUSPICIOUS)
    assert audio.judge(audio.VoiceScore(primary=-5.0, second=-1.0), cal) == ("fake", Strength.STRONG_SUSPICIOUS)
    assert audio.judge(audio.VoiceScore(primary=-1.0, second=2.0), cal) == ("disagree", None)
    assert audio.judge(audio.VoiceScore(primary=1.0, second=2.0), cal) == ("real", None)
    assert audio.judge(audio.VoiceScore(primary=-1.0), None) == ("unknown", None)              # not calibrated: say nothing


def test_voice_layer_never_says_a_voice_is_real(monkeypatch):
    monkeypatch.setattr(audio, "calibration", lambda: {"primary": {"threshold": 0.0, "strong_threshold": -3.0}})
    monkeypatch.setattr(audio, "score", lambda w: audio.VoiceScore(primary=2.0))
    lr = audio.voice_layer(tone())
    assert lr.signals == [] and lr.internal["band"] == "real"
    monkeypatch.setattr(audio, "score", lambda w: audio.VoiceScore(primary=-4.0))
    lr = audio.voice_layer(tone())
    assert [s.code for s in lr.signals] == ["MEDIA_VOICE_SYNTHETIC"] and lr.signals[0].strength == Strength.STRONG_SUSPICIOUS
    assert audio.voice_layer(None).not_checked == ["audio"]


def test_signed_band_cannot_be_forged_or_reused_after_expiry(monkeypatch):
    tok = page.sign({"band": "fake", "strength": "strong_suspicious", "versions": {}, "exp": 2**31})
    assert page.verify(tok)["band"] == "fake"
    body, mac = tok.rsplit(".", 1)
    assert page.verify(body + "." + ("0" * len(mac))) is None
    assert page.verify(page.sign({"band": "fake", "exp": 1})) is None
    assert page.layer_from({"band": "real"}).signals == []


def _check(transcript: str, band: str, strength: str | None):
    c = TestClient(app)
    tok = page.sign({"band": band, "strength": strength, "versions": {"voice": "test"}, "exp": 2**31})
    r = c.post("/models/voice/check", data={"token": tok, "transcript": transcript}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/case/")
    return c.get("/api/v1" + r.headers["location"]).json()


@pytest.mark.parametrize("text", [SCAM_EN, SCAM_HI])
def test_scam_words_flag_the_note_and_a_cloned_voice_adds_the_voice_sign(text):
    cloned = _check(text, "fake", "strong_suspicious")
    genuine = _check(text, "real", None)
    assert cloned["tier"] in ("SUSPICIOUS", "HIGH_RISK") and "MEDIA_VOICE_SYNTHETIC" in cloned["reason_codes"]
    assert genuine["tier"] in ("SUSPICIOUS", "HIGH_RISK") and "MEDIA_VOICE_SYNTHETIC" not in genuine["reason_codes"]
    assert any(c.startswith(("PAYEE_", "OFFER_")) for c in genuine["reason_codes"])          # reasons come from the words


def test_no_words_gives_cant_tell():
    assert _check("   ", "fake", "strong_suspicious")["tier"] == Tier.CANT_TELL.value


def test_unreadable_audio_gives_cant_tell_through_the_handler():
    res = models_voice.check_voice(b"not audio at all")
    assert res.tier == Tier.CANT_TELL and res.kind == "voice"


def test_voice_page_renders_in_both_languages_and_rejects_bad_files():
    c = TestClient(app)
    assert 'name="file"' in c.get("/models/voice").text
    assert "वॉइस नोट जाँचें" in TestClient(app, cookies={"sp_lang": "hi"}).get("/models/voice").text
    r = c.post("/models/voice", files={"file": ("a.ogg", b"garbage", "audio/ogg")})
    assert r.status_code == 422 and "could not hear" in r.text
    r = c.post("/models/voice/check", data={"token": "bad.token", "transcript": "hi"})
    assert r.status_code == 400 and "expired" in r.text


@needs_ffmpeg
def test_upload_shows_the_transcript_before_checking(monkeypatch):
    monkeypatch.setattr(audio, "transcribe", lambda w: (SCAM_EN, "en"))      # the speech model is replaced; decoding is real
    monkeypatch.setattr(audio, "score", lambda w: audio.VoiceScore(primary=None))
    r = TestClient(app).post("/models/voice", files={"file": ("a.wav", wav_bytes(tone(2.0)), "audio/wav")})
    assert r.status_code == 200 and "Here&#39;s what we heard" in r.text and "alpha.gain88@ybl" in r.text
    assert 'name="token"' in r.text
