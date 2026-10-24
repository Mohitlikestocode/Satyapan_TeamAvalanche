"""PDFs and screenshots, built as real files in memory."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from satyapan.api.app import app
from satyapan.contracts.models import Tier
from satyapan.extract.ocr import engine_name
from satyapan.service import analyse_image, analyse_pdf

client = TestClient(app)


def make_pdf(lines, producer=None):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 780
    for line in lines:
        c.drawString(60, y, line)
        y -= 22
    c.save()
    data = buf.getvalue()
    if producer:
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
        w.add_metadata({"/Producer": producer})
        out = io.BytesIO()
        w.write(out)
        data = out.getvalue()
    return data


BAD_INVOICE = ["TAX INVOICE INV-2026-1042", "Total Rs 1,48,500", "Bank: ICICI Bank  A/c 50100XXXX7781", "IFSC: HDFC0001234",
               "Note: our bank account has changed. Please pay to the new account."]
GOOD_INVOICE = ["TAX INVOICE INV-2026-1043", "Total Rs 12,000", "Bank: HDFC Bank  A/c 50100XXXX7781", "IFSC: HDFC0001234"]


def test_invoice_with_mismatched_bank_code_is_suspicious():
    r = analyse_pdf(make_pdf(BAD_INVOICE))
    assert r.tier == Tier.SUSPICIOUS
    assert {"INVOICE_IFSC_MISMATCH", "OFFER_BANK_DETAILS_CHANGED"} <= set(r.verdicts["en"].reason_codes)


def test_genuine_invoice_has_no_red_flags():
    r = analyse_pdf(make_pdf(GOOD_INVOICE))
    assert r.tier == Tier.NO_RED_FLAGS


def test_online_pdf_editor_is_a_sign_when_there_is_a_bank_code():
    r = analyse_pdf(make_pdf(GOOD_INVOICE, producer="iLovePDF"))
    assert "PDF_EDIT_TRACES" in r.verdicts["en"].reason_codes and r.tier == Tier.SUSPICIOUS


def test_pdf_without_text_or_not_a_pdf_is_cant_tell():
    assert analyse_pdf(make_pdf([])).tier == Tier.CANT_TELL
    assert analyse_pdf(b"not a pdf at all").tier == Tier.CANT_TELL
    assert analyse_pdf(b"%PDF-1.4 garbage garbage").tier == Tier.CANT_TELL


def test_pdf_upload_runs_the_checks_and_the_page_renders():
    r = client.post("/api/v1/check", data={"kind": "pdf"}, files={"file": ("inv.pdf", make_pdf(BAD_INVOICE))}).json()
    assert r["mode"] == "engine" and r["tier"] == "SUSPICIOUS"
    assert "different bank" in client.get(r["result_url"]).text


def pay_screen(ref="4521 8890 11"):
    img = Image.new("RGB", (720, 900), (245, 246, 250))
    d = ImageDraw.Draw(img)
    try:
        big, mid = ImageFont.truetype("arial.ttf", 60), ImageFont.truetype("arial.ttf", 24)
    except OSError:
        pytest.skip("no TrueType font on this machine")
    d.text((60, 120), "Payment Successful", font=mid, fill=(20, 20, 20))
    d.text((60, 190), "Rs 9,090", font=big, fill=(20, 20, 20))
    d.text((60, 300), "To: Sharma Kirana  sharma.kirana@ybl", font=mid, fill=(60, 60, 60))
    d.text((60, 350), f"UPI Ref: {ref}", font=mid, fill=(60, 60, 60))
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


@pytest.mark.skipif(engine_name() is None, reason="no OCR engine installed")
def test_screenshot_with_a_malformed_payment_reference_is_flagged():
    r = analyse_image(pay_screen("4521 8890 11"))
    assert "PAYMENT_UTR_FORMAT" in r.verdicts["en"].reason_codes


@pytest.mark.skipif(engine_name() is None, reason="no OCR engine installed")
def test_screenshot_with_a_normal_reference_is_not_flagged_for_it():
    r = analyse_image(pay_screen("4521 8890 1123"))
    assert "PAYMENT_UTR_FORMAT" not in r.verdicts["en"].reason_codes


def test_image_with_nothing_readable_is_cant_tell():
    b = io.BytesIO()
    Image.new("RGB", (200, 200), (255, 255, 255)).save(b, "PNG")
    assert analyse_image(b.getvalue()).tier == Tier.CANT_TELL
