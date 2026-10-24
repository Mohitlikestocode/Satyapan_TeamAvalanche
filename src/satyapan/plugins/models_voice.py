"""Voice notes, end to end: decode -> local transcript -> the same payee and word checks as a message, plus the voice sign.

Registered as the handler for kind="voice", so POST /api/v1/check with a voice note (the website, the Telegram bot) gets a real
result. Unreadable audio, or no speech, gives CAN'T TELL. The audio and the transcript are never stored.
"""
from __future__ import annotations

from ..layers.l2_forensics import audio
from ..service import CaseResult, analyse_text


def check_voice(data: bytes, topic: str = "", case_id: str | None = None, transcript: str | None = None, layer=None) -> CaseResult:
    """Run a voice check. `transcript` and `layer` let the transcript-first page pass what the visitor confirmed."""
    if layer is None:
        wav = audio.decode(data)
        if wav is None:
            return analyse_text("", kind="voice", topic=topic, case_id=case_id, readable=False, extra_names=["voice"])
        layer = audio.voice_layer(wav)
        if transcript is None:
            t = audio.transcribe(wav)
            transcript = t[0] if t else ""
        del wav
    text = transcript or ""
    return analyse_text(text, kind="voice", topic=topic, case_id=case_id, extra_layers=[layer], extra_names=["voice"],
                        readable=bool(text.strip()))


def ready() -> bool:
    """True when this server can actually decode and transcribe voice notes."""
    return audio.ffmpeg_path() is not None and (audio.whisper_dir() / "model.bin").exists()


def _handler(data: bytes, topic: str, case_id: str) -> CaseResult | None:
    # None lets the core route fall back to its labelled sample page on servers without the voice stack installed
    return check_voice(data, topic, case_id) if ready() else None


def setup(registry) -> None:
    registry.add_handler("voice", _handler, "voice", "Voice note: what was said, and signs of a cloned voice",
                         "वॉइस नोट: क्या कहा गया, और क्लोन आवाज़ के संकेत")
    registry.add_footer("Services", "Check a voice note", "/models/voice")
