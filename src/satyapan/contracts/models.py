"""Typed contracts shared by every module (SPEC §4, §5, §12).

Everything that crosses a module boundary is defined here. Layers return `LayerResult`;
fusion is a pure function of typed signals. Text taken from user media is *data*: it only
ever appears in these types as `TextSpan.text` or a validated `Entity.value`, and is never
used to pick a template, a code path or a tier.
"""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

ParamValue = str | int | float | bool


class Tier(StrEnum):
    HIGH_RISK = "HIGH_RISK"
    SUSPICIOUS = "SUSPICIOUS"
    CANT_TELL = "CANT_TELL"
    NO_RED_FLAGS = "NO_RED_FLAGS"
    REGISTRY_HIT = "REGISTRY_HIT"


class Layer(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    GATE = "GATE"
    REGISTRY = "REGISTRY"
    FUSION = "FUSION"


MEDIA_LAYERS = frozenset({Layer.L1, Layer.L2})
CLAIM_LAYERS = frozenset({Layer.L3, Layer.L4})


class Strength(StrEnum):
    STRONG_SUSPICIOUS = "strong_suspicious"
    WEAK_SUSPICIOUS = "weak_suspicious"
    NONE = "none"
    WEAK_AUTHENTIC = "weak_authentic"
    STRONG_AUTHENTIC = "strong_authentic"

    @property
    def suspicious(self) -> bool:
        return self in (Strength.STRONG_SUSPICIOUS, Strength.WEAK_SUSPICIOUS)


class LayerStatus(StrEnum):
    OK = "ok"
    ABSTAIN = "abstain"
    TIMEOUT = "timeout"
    ERROR = "error"


class ItemKind(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    TEXT = "text"
    LINK = "link"


class Lang(StrEnum):
    EN = "en"
    HI = "hi"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Signal(_Frozen):
    """One piece of evidence. `code` must exist in reasons/catalogue.yaml."""

    layer: Layer
    code: str
    strength: Strength
    params: dict[str, ParamValue] = Field(default_factory=dict)
    evidence_ref: str | None = None  # e.g. "span:3", "frame:12", never raw text


class LayerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: Layer
    status: LayerStatus = LayerStatus.OK
    signals: list[Signal] = Field(default_factory=list)
    model_versions: dict[str, str] = Field(default_factory=dict)
    elapsed_ms: int = 0
    # Modalities this layer did NOT use (e.g. "audio" while its detector is uncalibrated). Names only, never scores.
    # Not a finding: fusion turns it into the neutral "what was not checked" line, never into a suspicion.
    not_checked: list[str] = Field(default_factory=list)
    # Raw scores / debug. Never serialised to users or evidence packs (bands only).
    internal: dict[str, object] = Field(default_factory=dict, exclude=True)

    def strongest(self) -> Strength:
        order = [Strength.STRONG_SUSPICIOUS, Strength.WEAK_SUSPICIOUS, Strength.NONE,
                 Strength.WEAK_AUTHENTIC, Strength.STRONG_AUTHENTIC]
        present = {s.strength for s in self.signals}
        return next((s for s in order if s in present), Strength.NONE)


class Fingerprints(_Frozen):
    sha256: str
    phashes: list[str] = Field(default_factory=list)  # 64-bit dHash/pHash hex, per keyframe
    audio_fp: str | None = None


class TextSpan(_Frozen):
    """Untrusted text pulled from media. Data only."""

    text: str
    source: Literal["ocr", "stt", "qr", "user_text"]
    lang: str | None = None
    t_start: float | None = None
    t_end: float | None = None
    confidence: float | None = None


EntityKind = Literal["upi_id", "bank_account", "ifsc", "phone", "url", "invite", "apk"]


class Entity(_Frozen):
    kind: EntityKind
    value: str  # already validated by the kind's pattern; still escaped on output
    source: Literal["ocr", "stt", "qr", "user_text"]
    span_index: int | None = None


class Extraction(BaseModel):
    spans: list[TextSpan] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    status: LayerStatus = LayerStatus.OK
    elapsed_ms: int = 0
    model_versions: dict[str, str] = Field(default_factory=dict)


class QualityReport(BaseModel):
    """Output of the quality gate. `usable_for_*` drive abstention, not tiers directly."""

    duration_s: float | None = None
    has_audio: bool = False
    has_video: bool = False
    has_speech: bool = False
    face_found: bool = False
    bitrate_kbps: float | None = None
    snr_db: float | None = None
    usable_for_forensics: bool = True
    usable_for_any: bool = True
    reasons: list[str] = Field(default_factory=list)  # QUALITY_* codes


class InboundItem(BaseModel):
    channel: Literal["telegram", "web", "cli", "whatsapp"]
    chat_id: str  # raw channel id; hashed immediately by the store
    kind: ItemKind
    text: str | None = None  # user text / pasted link
    media_path: Path | None = None  # quarantined upload; never trusted
    declared_mime: str | None = None  # ignored for decisions; magic bytes decide
    lang: Lang = Lang.EN


class NormalisedMedia(BaseModel):
    workdir: Path
    wav_16k: Path | None = None
    keyframes: list[Path] = Field(default_factory=list)
    duration_s: float | None = None


class AnalysisContext(BaseModel):
    """Everything a layer may read. Built by intake; layers never touch raw uploads."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: str
    item: InboundItem
    media: NormalisedMedia | None = None
    fingerprints: Fingerprints | None = None
    quality: QualityReport = Field(default_factory=QualityReport)
    lang: Lang = Lang.EN
    profile: str = "laptop"
    offline: bool = True
    deadline_s: float = 45.0


class RegistryMatch(_Frozen):
    kind: Literal["payee", "url", "sha256", "phash", "afp"]
    entry_id: int
    status: Literal["confirmed"] = "confirmed"


class ReasonRef(_Frozen):
    code: str
    params: dict[str, ParamValue] = Field(default_factory=dict)


class FusionInput(BaseModel):
    results: list[LayerResult]
    registry_matches: list[RegistryMatch] = Field(default_factory=list)
    quality: QualityReport = Field(default_factory=QualityReport)
    media_present: bool = True
    payees_confirmed_registered: bool | None = None  # None = no payee present


class FusionOutput(BaseModel):
    tier: Tier
    reasons: list[ReasonRef]  # priority-ordered, all of them
    manual_steps: bool = False
    notes: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    """What the user sees. No scores. Text rendered from templates only."""

    case_id: str
    tier: Tier
    lang: Lang
    headline: str
    reasons_text: list[str]
    action_text: str
    footer_text: str
    reason_codes: list[str]


# -- Layer / service protocols (the seams the parallel streams build behind) -------------------

class ExtractorProtocol(Protocol):
    def run(self, ctx: AnalysisContext) -> Extraction: ...


class MediaLayer(Protocol):  # L1, L2
    def run(self, ctx: AnalysisContext) -> LayerResult: ...


class ClaimLayer(Protocol):  # L3, L4
    def run(self, ctx: AnalysisContext, extraction: Extraction) -> LayerResult: ...


class RegistryProtocol(Protocol):
    def match(self, fingerprints: Fingerprints | None, entities: list[Entity]) -> list[RegistryMatch]: ...
