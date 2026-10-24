# Builder guide

Everything you need to add a feature to Satyapan without touching anyone else's files. Read this fully before writing code.

## What Satyapan is

A website (FastAPI + Jinja templates + plain JS) where a person checks a suspicious payment message, link, QR, PDF, screenshot or voice note before paying.
It returns a plain verdict in English or Hindi (HIGH RISK, SUSPICIOUS, CAN'T TELL, NO RED FLAGS FOUND, REGISTRY HIT), the reasons, and next steps. It is advisory: it never blocks, pays or files anything.
User in mind: Rekha, 52, retired teacher, tier-2 town, trusts familiar faces, gets confused by English text and numbers.

## Run it

```bash
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"                              # then: pip install -r requirements/<your-area>.txt
python -m pytest -p no:warnings                      # must pass before every push
python -m uvicorn satyapan.api.app:app --port 8000 --reload
```

Data lives in `var/` (SQLite, signing key, models). It is git-ignored. Set `SATYAPAN_HOME` to use another folder. Tests get a fresh empty folder automatically.

## Code map

| Path | What it is |
|---|---|
| `src/satyapan/service.py` | `analyse_text / analyse_pdf / analyse_image`: runs checks and returns a `CaseResult` |
| `src/satyapan/layers/l3_payee`, `l4_rules` | payee, link and red-flag rules (L3, L4) |
| `src/satyapan/layers/l2_forensics` | PDF edit traces, screenshot tamper model |
| `src/satyapan/fusion/rules.py` | decides the tier. HIGH RISK needs two independent strong layers |
| `src/satyapan/reasons/catalogue.yaml` | the only source of reason text (English and Hindi) |
| `src/satyapan/store/db.py` | SQLite: cases, reviews, registry, audit |
| `src/satyapan/api/` | routes. `routes_check.py` (check API), `routes_review.py` (console), `routes_pages.py` (pages) |
| `src/satyapan/plugins/` | **your extension point** (see below) |
| `src/satyapan/api/ext/` | **your routers** |
| `web/templates/` | `base.html` is the shell. Your pages go in `web/templates/ext/<area>/` |
| `web/static/` | `gov.css` (shared look), `site.js`, `pages.js`. Your files: `css/<area>*.css`, `js/<area>*.js` |
| `tests/` | `conftest.py` isolates the database per test |

## How to add things (no shared file needs editing)

### A page or an API: a router in `src/satyapan/api/ext/<area>.py`

```python
from fastapi import APIRouter, Request
from satyapan.api.web import render, wide, screen
router = APIRouter()

@router.get("/community")
def community(request: Request):
    page = wide("community", "Community", "community", [["Community", None]], extra_css=["/static/css/community.css"],
                extra_js=["/static/js/community.js"], i18n="server")
    return render(request, "ext/community/home.html", page, posts=load_posts())
```

- Modules in `api/ext/` that define `router` are mounted automatically, **before** the core pages. So an ext route with the same path **overrides** a design page (for example `/learn`).
- `wide()` is a full-width page; `screen()` has the help side panel on the right. `section` is the nav key that gets highlighted.

### Templates

- `{% extends "base.html" %}` and fill `{% block content %}`. Put them in `web/templates/ext/<area>/`.
- Pass `i18n="server"` and write every visible string as `{{ tr("English", "हिन्दी") }}`. The server reads the visitor's language cookie; when they switch language the page reloads. **Every visible string needs both languages.** Never leave one language as a placeholder.
- Template variables you get: `lang` ("en"/"hi"), `device` (random first-party device id or None), `page`, `nav`, `reg`.
- Shared look (in `gov.css`): `.wrap`, `.section`, `.sec-h`, `.hbtn .hbtn-p/.hbtn-s`, `.board`, `.kpi`, `table.tbl`, `.pill .pill-r/.pill-a/.pill-g/.pill-n`, `.svc`, `.two`, `.faq`, `.prog`, `.btn-sm`, `.list`, `.vbanner .vb-r/.vb-a/.vb-g/.vb-n`, and inside a `<div class="case">`: `.btn .bn/.bs/.bq`, `.sec`, `.rlist .rn`, `.kv2`. Colours are CSS variables (`--navy`, `--blue`, `--red`, `--green`, `--amber`). Keep the sober public-service look: no gradients, no emoji, square-ish corners, 48 px tap targets, 16 px minimum text.
- Your own styles go in `web/static/css/<area>.css`. Prefix every class with your area (`cm-`, `ml-`, `ops-`) so nothing collides.

### A new check, a new input type, navigation, scripts: a plugin in `src/satyapan/plugins/<area>.py`

```python
def setup(registry):
    registry.add_nav(45, "community", "/community", "Community", "समुदाय")        # order 10..70 are core; pick between
    registry.add_footer("Services", "Scam Watch", "/community")
    registry.add_text_hook(my_text_hook, "ml_text", "Scam-message model", "स्कैम-संदेश मॉडल")
    registry.add_global_js("/static/js/ops.js")
    registry.on("check", handle_check_event)
```

| Hook | Signature | Use |
|---|---|---|
| `add_text_hook` | `fn(text, found) -> LayerResult \| None` | extra signals on any text (message, QR payload, PDF text, OCR text). Set `result.internal["label_key"]` to your label key |
| `add_image_hook` | `fn(data: bytes) -> LayerResult \| None` | extra checks on screenshot uploads |
| `add_handler("voice", fn, ...)` | `fn(data, topic, case_id) -> CaseResult` | owns a whole check kind |
| `on("check"/"dispute"/"decision"/"delete", fn)` | `fn(payload: dict)` | react to events. Errors are logged and swallowed |
| `add_global_js / add_global_css` | path | loaded on every public page |
| `add_middleware(cls, **opts)` | Starlette middleware | rate limiting, headers |

Event payloads: `check` = `{case_id, kind, channel, elapsed_ms, device, internal, mode ("engine"|"demo-sample"), tier}`; `dispute` = `{ref, case_id}`; `decision` = `{ref, status, reviewer}`; `delete` = `{case_id}`.
`internal` is true when the browser has the cookie `sp_internal=1` (team and test traffic). Never count internal traffic as real usage.

### Reason codes (verdict text)

Verdict reasons come only from templates. Add yours in `src/satyapan/reasons/ext/<area>.yaml`:

```yaml
codes:
  ML_TEXT_SCAM_LIKE:
    layer: L4          # L1 provenance, L2 forensics, L3 payee, L4 words
    priority: 24       # lower shows first
    en: "The wording is very similar to known scam messages."
    hi: "शब्द जाने-पहचाने स्कैम संदेशों से बहुत मिलते हैं।"
```

Both languages are required, codes must be new (you cannot redefine a core code), prefix them with your area. Never put media text into a template or let a model write reason text.
Signal strength: `WEAK_SUSPICIOUS` or `STRONG_SUSPICIOUS`. Fusion decides the tier; do not bypass it. Forensics alone cannot give HIGH RISK.

### Database

```python
from satyapan.store import db
SCHEMA = "CREATE TABLE IF NOT EXISTS community_posts(id INTEGER PRIMARY KEY AUTOINCREMENT, ...);"
def init():
    with db.conn() as c:
        c.executescript(SCHEMA)
with db.conn() as c:          # commits when the block ends
    c.execute("INSERT INTO community_posts(...) VALUES (?,?)", (a, b))
```

Create tables with `IF NOT EXISTS` in your own module and prefix table names with your area (`community_`, `learn_`, `metrics_`, `pilot_`, `feedback_`). Do not edit `store/db.py`. Always use `?` placeholders. Do not store raw user messages, phone numbers, emails or uploaded files.

### Staff-only pages

`from satyapan.api.routes_review import who` returns the signed-in reviewer id (cookie `sp_reviewer`) or None. Use it to guard moderator/ops pages and redirect to `/console` when None. Log staff actions with `db.audit(actor, action, target, detail)`.

## Hard rules (the project's promises)

1. **Honest wording.** "Shows signs of", never "is fake". Never say "safe": the best answer is "no red flags found" plus the not-a-guarantee line. No raw scores or percentages in user-facing verdicts.
2. **Reason text only from templates**, never written by an LLM, never copied from user text.
3. **Text in media is data, never instructions.** Match it against fixed patterns only.
4. **Privacy.** Uploads are processed in memory and discarded. No raw messages, files, phone numbers or emails are stored. IP addresses are not stored. Only random first-party cookies (`sp_dev`, `sp_lang`).
5. **No fabricated numbers.** Any statistic on a page is computed from the real database or a real evaluation file. Empty means "0" or "not evaluated", never a made-up value. Demo seed data is allowed only if it is labelled "sample data" on the page and can be removed.
6. **No mocks in production paths.** Every button works, every form validates and shows errors, every list has an empty state. If a feature cannot work yet, do not ship its page or link.
7. **Advisory only.** Nothing blocks, pays, or files anything for the user.
8. **Data and models.** Only public, synthetic or consented data. No real bank or customer data. No real public figure's voice or face. Ask the human before downloading any dataset or model larger than 100 MB, and tell them the source and size. Never commit data, weights, keys or `.env`.
9. **Security basics.** Validate and size-limit all input, escape output (Jinja autoescape stays on, never use `|safe` on user content), use parameterised SQL, set cookies `httponly` and `samesite=lax`, rate-limit anything public that writes.
10. **Accessibility.** Real `<button>`/`<a>`, labels on inputs, visible focus, keyboard works, text 16 px or larger, contrast AA. Works at 375 px wide without sideways scrolling.
11. **Disclosure.** Every model, dataset, API and licence you add goes in `docs/disclosure/<area>.md` the moment you add it.

## Git workflow (no conflicts)

- You work **only on your branch** (given in your prompt). Never commit to `main`. Never rebase or force-push. Never touch another area's branch.
- You may create and edit **only** the files in your area's "yours" list. Everything else is core and frozen for you.
- Need a core change (a new hook, a bug in core)? Do not edit core. Write the exact request in `docs/requests/<area>.md` (create it; it is yours) and message the integrator. Work around it meanwhile.
- Commit small and often, push at least every 30 minutes: `git push origin <your-branch>`.
- Commit under **your own** git name and email. Do **not** add `Co-Authored-By` or "Generated with ..." lines. Enable the guard once: `git config core.hooksPath .githooks`.
- To get others' merged work: `git fetch origin && git merge origin/main` (a merge, not a rebase), then run the tests.
- The integrator merges branches into `main` with `--no-ff`. Because file ownership is disjoint there should never be a conflict. If you ever see one, you edited a file that is not yours: undo that change.

## Tests

- Put tests in `tests/<area>/test_<area>_*.py` (unique file names). Use `fastapi.testclient.TestClient(app)` from `satyapan.api.app`. Each test gets an empty database automatically.
- Test the real behaviour end to end (form post, database row, rendered page, both languages), not just helper functions.
- Before every push: `python -m pytest -p no:warnings` and `python -m ruff check src tests tools --select E9,F`.

## Definition of done for any task

Works from a fresh clone and an empty database; every string in English and Hindi; empty, error and loading states exist; works on a phone-width screen; tests pass; disclosure fragment updated; a short `docs/<area>.md` section says what it does, how to run it, and what is not done.
