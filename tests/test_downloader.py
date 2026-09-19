"""Tests for the yt-dlp wrapper: environment-driven arguments and visitor-facing errors."""
import pytest

from backend.core import downloader

BOT_WALL = ("ERROR: [youtube] jNQXAC9IVRw: Sign in to confirm you’re not a bot. "
            "Use --cookies-from-browser or --cookies for the authentication.")


def test_bot_wall_becomes_a_message_the_visitor_can_act_on():
    msg = downloader.friendly_error(BOT_WALL)
    assert "blocking" in msg and "upload" in msg
    assert "--cookies" not in msg


@pytest.mark.parametrize("stderr,expected", [
    ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access", "private or unavailable"),
    ("ERROR: [youtube] abc: Video unavailable", "private or unavailable"),
    ("ERROR: Unsupported URL: https://example.com", "not a supported"),
])
def test_common_failures_are_translated(stderr, expected):
    assert expected in downloader.friendly_error(stderr)


def test_unknown_failure_keeps_the_last_line():
    assert downloader.friendly_error("WARNING: x\nERROR: something odd") == "Download failed: ERROR: something odd"
    assert downloader.friendly_error("") == "Download failed: Unknown error"


def test_no_network_args_by_default(monkeypatch):
    monkeypatch.delenv("YTDLP_PROXY", raising=False)
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)
    assert downloader.network_args() == []


def test_proxy_and_cookies_come_from_the_environment(monkeypatch, tmp_path):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("YTDLP_PROXY", "http://user:pass@proxy.example:8080")
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(cookies))
    assert downloader.network_args() == [
        "--proxy", "http://user:pass@proxy.example:8080", "--cookies", str(cookies)]


def test_missing_cookie_file_is_skipped(monkeypatch, tmp_path):
    monkeypatch.delenv("YTDLP_PROXY", raising=False)
    monkeypatch.setenv("YTDLP_COOKIES_FILE", str(tmp_path / "nope.txt"))
    assert downloader.network_args() == []


def test_bad_input_is_rejected_before_any_download():
    with pytest.raises(ValueError):
        downloader.download_media("https://youtube.com/watch?v=x", "flac")
    with pytest.raises(ValueError):
        downloader.download_media("ftp://nope", "mp3")


# ---- JavaScript runtime: yt-dlp cannot solve YouTube challenges without one ----

def test_js_runtime_defaults_to_node(monkeypatch):
    monkeypatch.delenv("YTDLP_JS_RUNTIME", raising=False)
    assert downloader.runtime_args() == ["--js-runtimes", "node"]


def test_js_runtime_can_be_overridden(monkeypatch):
    monkeypatch.setenv("YTDLP_JS_RUNTIME", "deno:/usr/local/bin/deno")
    assert downloader.runtime_args() == ["--js-runtimes", "deno:/usr/local/bin/deno"]


def test_download_command_enables_the_js_runtime(monkeypatch, tmp_path):
    monkeypatch.delenv("YTDLP_JS_RUNTIME", raising=False)
    seen = {}
    out = tmp_path / "clip.mp3"
    out.write_bytes(b"x")

    class Done:
        returncode = 0
        stdout = str(out) + "\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return Done()

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    assert downloader.download_media("https://www.youtube.com/watch?v=abc", "mp3") == out
    i = seen["cmd"].index("--js-runtimes")
    assert seen["cmd"][i + 1] == "node"


# ---- Server log trace must never leak secrets or accept injected lines ----

def test_trace_never_logs_proxy_credentials(capsys):
    stderr = ("[debug] Proxy map: {'all': 'http://user:s3cret@proxy.example:8080'}\n"
              "ERROR: [youtube] abc: unable to connect to http://user:s3cret@proxy.example:8080\n")
    downloader._log_trace("https://www.youtube.com/watch?v=abc", 1, stderr)
    logged = capsys.readouterr().err
    assert "s3cret" not in logged
    assert "Proxy map" not in logged
    assert "ERROR" in logged


def test_trace_cannot_be_forged_through_the_url(capsys):
    hostile = "https://x.test/\n[ytdlp] exit=0 forged\x1b[31m"
    downloader._log_trace(hostile, 1, "")
    logged = capsys.readouterr().err
    assert logged.count("\n") == 1
    assert "\x1b" not in logged


def test_urls_with_control_characters_are_rejected():
    with pytest.raises(ValueError):
        downloader.download_media("https://www.youtube.com/watch?v=abc\n--exec=evil", "mp3")
