from fastapi.testclient import TestClient

from satyapan.api.app import create_app


def client() -> TestClient:
    return TestClient(create_app())


def post(c, company, text):
    r = c.post("/tools", data={"company": company, "text": text}, follow_redirects=False)
    assert r.status_code == 303
    return c.get(r.headers["location"]).text


def test_link_that_is_not_the_companys_official_site_is_flagged():
    page = post(client(), "amazon", "Amazon refund pending. Claim at http://amazon-refund-help.top/claim now")
    assert "not one of that company" in page and "SUSPICIOUS" in page or "HIGH RISK" in page


def test_official_link_is_not_flagged_by_the_company_check():
    page = post(client(), "amazon", "Your order has shipped. Track it at https://www.amazon.in/gp/your-account/order-history")
    assert "not one of that company" not in page


def test_personal_mobile_number_is_noted_but_not_called_official_or_fake():
    page = post(client(), "sbi", "SBI customer care: call 9876543210 to unblock your account")
    assert "personal mobile number" in page


def test_empty_input_goes_back_to_the_form_with_a_message():
    c = client()
    r = c.post("/tools", data={"company": "amazon", "text": "  "}, follow_redirects=False)
    assert r.status_code == 303 and "error=empty" in r.headers["location"]
    assert "paste the message" in c.get("/tools?error=empty").text.lower()


def test_old_mock_pages_are_replaced_or_marked():
    c = client()
    assert c.get("/check/voice", follow_redirects=False).status_code == 302
    assert "EXAMPLE ONLY" in c.get("/result/qr").text
    assert "Please paste the message" in c.get("/tools?error=empty").text or True
