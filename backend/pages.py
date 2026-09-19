"""Server-side page assembly.

Pages are plain HTML files with a few comment placeholders. This module fills in
the shared partials, stamps asset URLs with a version for cache-busting, and
injects Google AdSense tags when the site owner has configured them.

AdSense is controlled by two environment variables, read on every request so a
change in the hosting dashboard takes effect without a code change:

    ADSENSE_CLIENT   publisher id, for example ca-pub-1234567890123456
    ADSENSE_SLOT     ad unit id, digits only. Optional. Without it only the
                     head script is added, which is enough for Auto ads.
"""
import os
import re
from pathlib import Path

from fastapi.responses import HTMLResponse

STATIC_DIR = Path(__file__).resolve().parent / "static"
PARTIALS_DIR = STATIC_DIR / "partials"

SITE_URL = os.getenv("SITE_URL", "https://audionlabs.ai").rstrip("/")

# Public pages, in sitemap order: (path, html file, nav key, ads allowed)
# Ads never load on the downloader page or on the legal pages.
PAGES = [
    ("/", "index.html", "home", True),
    ("/slowed-reverb", "slowed-reverb.html", "slowed", True),
    ("/stems", "stems.html", "stems", True),
    ("/transcribe", "transcribe.html", "transcribe", True),
    ("/youtube-downloader", "youtube-downloader.html", "download", False),
    ("/privacy", "privacy.html", "", False),
    ("/terms", "terms.html", "", False),
]

_CLIENT_RE = re.compile(r"^ca-pub-\d{10,20}$")
_SLOT_RE = re.compile(r"^\d{6,20}$")


def adsense_client() -> str:
    """The configured publisher id, or an empty string if unset or malformed."""
    value = os.getenv("ADSENSE_CLIENT", "").strip()
    return value if _CLIENT_RE.match(value) else ""


def adsense_slot() -> str:
    value = os.getenv("ADSENSE_SLOT", "").strip()
    return value if _SLOT_RE.match(value) else ""


def asset_version() -> str:
    """Newest modification time across static assets, used as a cache-busting stamp."""
    newest = 0
    for folder in (STATIC_DIR, PARTIALS_DIR):
        for path in folder.iterdir():
            if path.is_file():
                newest = max(newest, int(path.stat().st_mtime))
    return str(newest)


def _partial(name: str) -> str:
    return (PARTIALS_DIR / name).read_text(encoding="utf-8")


def _nav(active: str) -> str:
    nav = _partial("nav.html")
    if active:
        for cls in ("nav-item", "tab"):
            nav = nav.replace(
                f'class="{cls}" data-nav="{active}"',
                f'class="{cls} active" aria-current="page" data-nav="{active}"',
            )
    return nav


def _adsense_head(client: str) -> str:
    return (
        f'  <meta name="google-adsense-account" content="{client}">\n'
        f'  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
        f'?client={client}" crossorigin="anonymous"></script>'
    )


def _ad_unit(client: str, slot: str) -> str:
    return (
        '<div class="ad-wrap">'
        f'<ins class="adsbygoogle" style="display:block" data-ad-client="{client}" '
        f'data-ad-slot="{slot}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
        "<script>(adsbygoogle = window.adsbygoogle || []).push({});</script>"
        "</div>"
    )


def render_page(filename: str, active: str = "", ads: bool = True) -> HTMLResponse:
    html = (STATIC_DIR / filename).read_text(encoding="utf-8")

    client = adsense_client() if ads else ""
    slot = adsense_slot() if client else ""

    html = html.replace("<!-- HEAD_COMMON -->", _partial("head.html").rstrip("\n"))
    html = html.replace("<!-- SPRITE -->", _partial("sprite.html"))
    html = html.replace("<!-- NAV -->", _nav(active))
    html = html.replace("<!-- FOOTER -->", _partial("footer.html"))
    html = html.replace("<!-- ADSENSE_HEAD -->", _adsense_head(client) if client else "")
    html = html.replace("<!-- AD_SLOT -->", _ad_unit(client, slot) if client and slot else "")
    html = html.replace("__V__", asset_version())

    return HTMLResponse(html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


def ads_txt() -> str:
    """ads.txt body for the configured publisher, or an empty string if none."""
    client = adsense_client()
    if not client:
        return ""
    publisher = client[len("ca-"):]
    return f"google.com, {publisher}, DIRECT, f08c47fec0942fa0\n"


def robots_txt() -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n"


def sitemap_xml() -> str:
    urls = "".join(f"  <url><loc>{SITE_URL}{path}</loc></url>\n" for path, *_ in PAGES)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )
