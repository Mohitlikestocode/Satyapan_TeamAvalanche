"""Hidden-word check: tricks are undone so the real rules see the words; ordinary text is left alone."""
from satyapan.eval import attacks
from satyapan.layers.l4_semantic.normalise import normalise
from satyapan.plugins import load_plugins
from satyapan.service import analyse_text

SCAM = "Guaranteed 30% profit every month. Pay Rs 25000 to alpha.gain88@ybl to join."


def test_tricks_are_undone():
    assert normalise(attacks.homoglyph(SCAM)).text == SCAM
    assert "alpha.gain88@ybl" in normalise(attacks.split_upi(SCAM)).text
    n = normalise(attacks.spacing(SCAM))
    assert "Guaranteed" in n.text and "spread_letters" in n.tricks
    assert set(normalise(attacks.everything(SCAM)).tricks) >= {"lookalike", "split_upi"}


def test_ordinary_text_has_no_tricks():
    for t in ["Meet me at 5 pm at the gate", "R K Traders paid Rs 500", "Your OTP is 4521. Do not share it.", "email me at ravi@gmail.com",
              "नमस्ते, आपका पार्सल आज आएगा", "U.S.A trip next week", "Please do K.Y.C at the branch", "क्या‍आप आ रहे हैं?"]:
        assert normalise(t).tricks == [], t
    assert normalise("Please do K.Y.C at the branch").text == "Please do KYC at the branch"   # joined, but not a warning sign
    assert normalise("क्या‍आप").text == "क्या‍आप"                                    # Devanagari joiners are kept


def test_hidden_words_are_caught_and_say_why():
    load_plugins()
    for fn in (attacks.homoglyph, attacks.split_upi, attacks.spacing):
        res = analyse_text(fn(SCAM), use_registry=False)
        assert res.tier.value in ("SUSPICIOUS", "HIGH_RISK"), fn.__name__
        assert "ml_hidden_words" in res.layers_run
    res = analyse_text(attacks.homoglyph(SCAM), use_registry=False)
    assert "ML_TEXT_OBFUSCATED" in res.verdicts["en"].reason_codes
    assert "hides its words" in " ".join(res.verdicts["en"].reasons_text)
    assert "ml_hidden_words" not in analyse_text("Your parcel arrives today.", use_registry=False).layers_run
