"""Labels for the company-claim check shown under "What we checked" on a result page."""
from __future__ import annotations


def setup(registry) -> None:
    registry.layer_labels["brand"] = ("The company it claims to be: its links and phone numbers against that company's official addresses",
                                      "जिस कंपनी का दावा है: उसके लिंक और फ़ोन नंबर, उस कंपनी के आधिकारिक पतों से मिलाकर")
