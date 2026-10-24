from pathlib import Path

import yaml

from satyapan.contracts.models import Tier


def test_tiers():
    assert {t.value for t in Tier} == {"HIGH_RISK", "SUSPICIOUS", "CANT_TELL", "NO_RED_FLAGS", "REGISTRY_HIT"}


def test_catalogue_loads():
    p = Path(__file__).parents[1] / "src/satyapan/reasons/catalogue.yaml"
    assert yaml.safe_load(p.read_text(encoding="utf-8"))["codes"]
