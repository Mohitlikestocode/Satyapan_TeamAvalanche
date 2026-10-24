"""Extension points. Add a feature by dropping files in your own folders; no shared core file needs editing.

How it works
- Any module in this package (`satyapan/plugins/*.py`, name not starting with "_") that defines `setup(registry)` is imported at startup.
  Call the `registry.add_*` / `registry.on` helpers there.
- Any module in `satyapan/api/ext/*.py` that defines `router` (a FastAPI APIRouter) is mounted at startup. Ext routers are mounted
  BEFORE the core page routes, so an ext route with the same path overrides the design page (for example `/learn`).
- Reason codes: add `src/satyapan/reasons/ext/<area>.yaml` with `codes:` (and optionally `triggers:`). They are merged into the catalogue.

Hooks (all optional, all must be fast, return None to stay silent, and must never raise on bad input):
- text hook   fn(text: str, found: Found) -> LayerResult | None       runs on every message/link/QR text/PDF text/OCR text
- image hook  fn(data: bytes) -> LayerResult | None                    runs on screenshot uploads
- handler     fn(data: bytes, topic: str, case_id: str) -> CaseResult  owns a whole check kind, for example "voice"
- listener    fn(payload: dict) -> None   for events: "check", "dispute", "decision", "delete"   (errors are swallowed and logged)

A hook's LayerResult may only carry signals whose `code` exists in the catalogue. Text taken from media is data: never use it to pick
a template or a tier. Reason text always comes from the catalogue.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from collections import defaultdict
from collections.abc import Callable
from typing import Any

log = logging.getLogger("satyapan.plugins")


class Registry:
    def __init__(self) -> None:
        self._nav: list[tuple[int, str, str, str, str]] = []
        self._footer: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.text_hooks: list[Callable] = []
        self.image_hooks: list[Callable] = []
        self.handlers: dict[str, Callable] = {}
        self.listeners: dict[str, list[Callable]] = defaultdict(list)
        self.global_js: list[str] = []
        self.global_css: list[str] = []
        self.middlewares: list[tuple[type, dict[str, Any]]] = []
        self.layer_labels: dict[str, tuple[str, str]] = {}
        self.related: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.loaded: list[str] = []

    # ---- navigation and footer -------------------------------------------------------------------------------
    def add_nav(self, order: int, key: str, href: str, label_en: str, label_hi: str) -> None:
        """Add a top-menu item. Core items use orders 10 (Home) to 70 (How it works). Pick an order between them."""
        self._nav.append((order, key, href, label_en, label_hi))

    def add_footer(self, column: str, label: str, href: str) -> None:
        """column is one of: "Services", "If you paid", "Learn and about", or a new title."""
        self._footer[column].append((label, href))

    def nav(self, core: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]]:
        items = [((i + 1) * 10, *row) for i, row in enumerate(core)] + self._nav
        return [row[1:] for row in sorted(items, key=lambda r: (r[0], r[1]))]

    def footer_extra(self, column: str) -> list[tuple[str, str]]:
        return list(self._footer.get(column, []))

    def footer_new_columns(self, known: set[str]) -> dict[str, list[tuple[str, str]]]:
        return {k: v for k, v in self._footer.items() if k not in known}

    # ---- checks ----------------------------------------------------------------------------------------------
    def add_text_hook(self, fn: Callable, label_key: str, label_en: str, label_hi: str) -> None:
        """label_* describe what the hook checked, shown on the result page under "What we checked"."""
        self.text_hooks.append(fn)
        self.layer_labels[label_key] = (label_en, label_hi)

    def add_image_hook(self, fn: Callable, label_key: str, label_en: str, label_hi: str) -> None:
        self.image_hooks.append(fn)
        self.layer_labels[label_key] = (label_en, label_hi)

    def add_handler(self, kind: str, fn: Callable, label_key: str, label_en: str, label_hi: str) -> None:
        self.handlers[kind] = fn
        self.layer_labels[label_key] = (label_en, label_hi)

    # ---- events and page extras ------------------------------------------------------------------------------
    def on(self, event: str, fn: Callable[[dict], None]) -> None:
        self.listeners[event].append(fn)

    def emit(self, event: str, payload: dict) -> None:
        for fn in list(self.listeners.get(event, [])):
            try:
                fn(payload)
            except Exception:  # a listener must never break the user's request
                log.exception("listener for %s failed", event)

    def add_global_js(self, path: str) -> None:
        """Script loaded on every public page, for example "/static/js/traction.js"."""
        self.global_js.append(path)

    def add_global_css(self, path: str) -> None:
        self.global_css.append(path)

    def add_middleware(self, cls: type, **options: Any) -> None:
        self.middlewares.append((cls, options))

    def add_related(self, section: str, label: str, href: str) -> None:
        self.related[section].append((label, href))


REGISTRY = Registry()
_LOADED = False


def load_plugins(package: str = "satyapan.plugins", registry: Registry | None = None) -> list[str]:
    """Import every plugin module once and let it register itself."""
    global _LOADED
    reg = registry or REGISTRY
    if registry is None and _LOADED:
        return reg.loaded
    pkg = importlib.import_module(package)
    for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda x: x.name):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{package}.{m.name}")
        if hasattr(mod, "setup"):
            mod.setup(reg)
            reg.loaded.append(m.name)
    if registry is None:
        _LOADED = True
    return reg.loaded


def include_ext_routers(app, package: str = "satyapan.api.ext") -> list[str]:
    """Mount `router` from every module in the ext package."""
    pkg = importlib.import_module(package)
    mounted = []
    for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda x: x.name):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{package}.{m.name}")
        if hasattr(mod, "router"):
            app.include_router(mod.router)
            mounted.append(m.name)
    return mounted
