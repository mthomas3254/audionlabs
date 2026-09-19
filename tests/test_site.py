"""Tests for page assembly, AdSense injection, and the JS-to-HTML id contract."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import pages
from backend.main import app

STATIC = Path(__file__).resolve().parents[1] / "backend" / "static"
PLACEHOLDERS = ["<!-- NAV -->", "<!-- FOOTER -->", "<!-- SPRITE -->", "<!-- HEAD_COMMON -->",
                "<!-- ADSENSE_HEAD -->", "<!-- AD_SLOT -->", "__V__"]
CLIENT = "ca-pub-1234567890123456"
SLOT = "9876543210"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("ADSENSE_CLIENT", raising=False)
    monkeypatch.delenv("ADSENSE_SLOT", raising=False)
    return TestClient(app)


@pytest.mark.parametrize("path", [p[0] for p in pages.PAGES])
def test_every_page_renders_with_no_leftover_placeholders(client, path):
    res = client.get(path)
    assert res.status_code == 200
    assert 'class="nav"' in res.text
    assert "<footer>" in res.text
    for marker in PLACEHOLDERS:
        assert marker not in res.text, f"{marker} left in {path}"
    assert re.search(r"/static/style\.css\?v=\d+", res.text)


@pytest.mark.parametrize("path,key", [(p[0], p[2]) for p in pages.PAGES if p[2]])
def test_exactly_one_nav_item_is_active(client, path, key):
    html = client.get(path).text
    assert f'class="nav-item active" aria-current="page" data-nav="{key}"' in html
    assert f'class="tab active" aria-current="page" data-nav="{key}"' in html
    assert html.count('class="nav-item active"') == 1


def test_no_ads_anywhere_until_configured(client):
    for path, *_ in pages.PAGES:
        assert "adsbygoogle" not in client.get(path).text
    assert client.get("/ads.txt").status_code == 404


@pytest.mark.parametrize("path", [p[0] for p in pages.PAGES])
def test_ads_appear_on_every_page_when_configured(client, monkeypatch, path):
    monkeypatch.setenv("ADSENSE_CLIENT", CLIENT)
    monkeypatch.setenv("ADSENSE_SLOT", SLOT)
    monkeypatch.delenv("ADSENSE_EXCLUDE", raising=False)
    html = client.get(path).text
    assert html.count(f"adsbygoogle.js?client={CLIENT}") == 1, "head script must load exactly once"
    assert f'<meta name="google-adsense-account" content="{CLIENT}">' in html
    assert f'data-ad-slot="{SLOT}"' in html, f"no ad unit on {path}"
    # every unit pushes itself exactly once
    assert html.count("<ins class=\"adsbygoogle\"") == html.count("adsbygoogle || []).push({})")


def test_landing_page_carries_two_ad_units(client, monkeypatch):
    monkeypatch.setenv("ADSENSE_CLIENT", CLIENT)
    monkeypatch.setenv("ADSENSE_SLOT", SLOT)
    assert client.get("/").text.count('<ins class="adsbygoogle"') == 2


def test_owner_can_switch_ads_off_for_chosen_pages(client, monkeypatch):
    monkeypatch.setenv("ADSENSE_CLIENT", CLIENT)
    monkeypatch.setenv("ADSENSE_SLOT", SLOT)
    monkeypatch.setenv("ADSENSE_EXCLUDE", "/youtube-downloader, /terms")
    assert "adsbygoogle" not in client.get("/youtube-downloader").text
    assert "adsbygoogle" not in client.get("/terms").text
    assert "adsbygoogle" in client.get("/stems").text
    assert "adsbygoogle" in client.get("/privacy").text


def test_client_without_slot_adds_head_script_only(client, monkeypatch):
    monkeypatch.setenv("ADSENSE_CLIENT", CLIENT)
    html = client.get("/").text
    assert f"adsbygoogle.js?client={CLIENT}" in html
    assert "data-ad-slot" not in html


@pytest.mark.parametrize("bad", ['"><script>alert(1)</script>', "pub-123", "ca-pub-abc", ""])
def test_malformed_publisher_id_is_ignored(client, monkeypatch, bad):
    monkeypatch.setenv("ADSENSE_CLIENT", bad)
    monkeypatch.setenv("ADSENSE_SLOT", SLOT)
    html = client.get("/").text
    assert "adsbygoogle" not in html
    assert "alert(1)" not in html
    assert client.get("/ads.txt").status_code == 404


def test_ads_txt_lists_the_publisher(client, monkeypatch):
    monkeypatch.setenv("ADSENSE_CLIENT", CLIENT)
    res = client.get("/ads.txt")
    assert res.status_code == 200
    assert res.text.strip() == "google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0"


def test_robots_and_sitemap(client):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200 and "Sitemap:" in robots.text
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    for path, *_ in pages.PAGES:
        assert f"<loc>{pages.SITE_URL}{path}</loc>" in sitemap.text


def test_health_and_static_assets(client):
    assert client.get("/health").json()["status"] == "ok"
    for name in ["style.css", "app.js", "audio-core.js", "studio.js", "mixer.js", "favicon.svg"]:
        assert client.get(f"/static/{name}").status_code == 200, name


def test_pages_load_the_scripts_they_need(client):
    slowed = client.get("/slowed-reverb").text
    assert slowed.index("audio-core.js") < slowed.index("studio.js")
    stems = client.get("/stems").text
    assert stems.index("audio-core.js") < stems.index("mixer.js") < stems.index("app.js")
    assert 'id="mixer"' in stems


# ---- Contract: every element id the scripts look up must exist in the page ----

def _ids_in(html: str) -> set:
    return set(re.findall(r'\bid="([^"]+)"', html))


def _section(js: str, start: str, end: str) -> str:
    a = js.index(start)
    b = js.index(end, a) if end else len(js)
    return js[a:b]


def test_studio_ids_exist_in_slowed_page(client):
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    wanted = set(re.findall(r'\$\("([^"]+)"\)', js))
    assert len(wanted) > 15
    missing = wanted - _ids_in(client.get("/slowed-reverb").text)
    assert not missing, f"slowed-reverb.html is missing ids: {sorted(missing)}"


@pytest.mark.parametrize("path,start,end", [
    ("/stems", "STEMS PAGE", "YOUTUBE DOWNLOADER PAGE"),
    ("/youtube-downloader", "YOUTUBE DOWNLOADER PAGE", "TRANSCRIBE PAGE"),
    ("/transcribe", "TRANSCRIBE PAGE", ""),
])
def test_app_js_ids_exist_in_their_page(client, path, start, end):
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    wanted = set(re.findall(r'getElementById\("([^"]+)"\)', _section(js, start, end)))
    assert len(wanted) > 10
    # opt-slowed is optional in app.js (guarded with `if (optSlowed)`).
    wanted.discard("opt-slowed")
    missing = wanted - _ids_in(client.get(path).text)
    assert not missing, f"{path} is missing ids: {sorted(missing)}"
