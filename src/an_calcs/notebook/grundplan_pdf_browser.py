"""Render the shared UI as a transparent vector PDF, never as a screenshot."""

from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import io
import math
from pathlib import Path

from pypdf import PdfReader

from .grundplan_html import render_html
from .grundplan_canvas import DEFAULT_BOUNDS, validate_bounds


def render_overlay(snapshot):
    background = snapshot["pages"][0]
    document = render_html(snapshot, pdf_mode=True).decode("utf-8")
    bounds = validate_bounds(snapshot["state"].get("canvas_bounds", DEFAULT_BOUNDS))
    width = background["width"] * (bounds["right"] - bounds["left"])
    height = background["height"] * (bounds["bottom"] - bounds["top"])
    # A Jupyter kernel already has an asyncio loop. Run the synchronous browser
    # renderer in its own worker, also closing it before the request finishes.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_render, document, width, height).result()


@lru_cache(maxsize=8)
def _render(document, width, height):
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError as exc:
        raise ImportError("PDF-export kräver Playwright. Uppdatera an-calcs[notebook].") from exc
    with sync_playwright() as runtime:
        # Use an installed browser when Playwright's Chromium is not installed.
        channels = [None, "chrome", "msedge"] if Path(runtime.chromium.executable_path).is_file() else ["chrome", "msedge", None]
        browser = None
        for channel in channels:
            try:
                browser = runtime.chromium.launch(channel=channel, headless=True, chromium_sandbox=True)
                break
            except Error:
                continue
        if browser is None:
            raise RuntimeError("PDF-export behöver Chromium, Google Chrome eller Microsoft Edge. "
                               "Installera Chromium med: python -m playwright install chromium")
        try:
            context = browser.new_context(viewport={"width": math.ceil(width), "height": math.ceil(height)}, locale="sv-SE",
                                          service_workers="block")
            # No network, user profile, drawing file or external fonts are loaded.
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.emulate_media(media="screen")
            page.set_content(document, wait_until="load")
            try:
                page.locator('html[data-pdf-ready="true"]').wait_for(state="attached", timeout=15000)
            except Error as exc:
                raise RuntimeError("PDF-layouten kunde inte skapas: " + (errors[0] if errors else "tidsgränsen överskreds")) from exc
            data = page.pdf(width=f"{width}px", height=f"{height}px", print_background=True,
                            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                            prefer_css_page_size=True, display_header_footer=False)
        finally:
            browser.close()
    pages = PdfReader(io.BytesIO(data)).pages
    if len(pages) != 1:
        raise RuntimeError("PDF-layouten måste rymmas på en enda ritningssida.")
    if pages[0].images:
        raise RuntimeError("PDF-exporten avbröts: etiketter och widgetar måste vara vektorer.")
    return data
