"""Real QR images, scanned with the same decoder the app uses, under phone-style damage."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("segno")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import make_qr_kit as kit  # noqa: E402

from satyapan.extract.qr import decode_qr  # noqa: E402


def to_bytes(img):
    import io
    b = io.BytesIO(); img.save(b, "PNG"); return b.getvalue()


@pytest.mark.parametrize("how", kit.CONDITIONS)
@pytest.mark.parametrize("name", list(kit.PAYLOADS))
def test_qr_decodes_under_damage(name, how):
    img = kit.degrade(kit.base_qr(kit.PAYLOADS[name]), how)
    assert decode_qr(to_bytes(img)) == [kit.PAYLOADS[name]]
