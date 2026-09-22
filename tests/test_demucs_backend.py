"""Stem separation backend selection: Modal GPU when configured, local CPU otherwise.

The GPU path must produce exactly the files the rest of the app expects
(stems_dir/{bass,drums,other,vocals}.wav), and must fall back to the CPU path
when the GPU service cannot be reached, so a Modal outage never breaks splits.
"""
from pathlib import Path

import pytest

from backend.core import demucs_engine as engine
from backend.services.file_manager import TrackPaths


@pytest.fixture()
def track(tmp_path):
    original = tmp_path / "in" / "song.mp3"
    original.parent.mkdir()
    original.write_bytes(b"ID3fake-audio")
    stems_dir = tmp_path / "stems"
    stems_dir.mkdir()
    return TrackPaths(track_id="t1", original_path=original, stems_dir=stems_dir,
                      slowed_dir=tmp_path / "slowed")


def fake_gpu_ok(audio: bytes, ext: str):
    assert audio == b"ID3fake-audio" and ext == ".mp3"
    return {name: b"RIFF" + name.encode() for name in ("bass", "drums", "other", "vocals")}


def test_backend_is_local_unless_configured(monkeypatch):
    monkeypatch.delenv("DEMUCS_BACKEND", raising=False)
    assert engine.backend() == "local"
    monkeypatch.setenv("DEMUCS_BACKEND", "modal")
    assert engine.backend() == "modal"
    monkeypatch.setenv("DEMUCS_BACKEND", "nonsense")
    assert engine.backend() == "local"


def test_gpu_backend_writes_the_same_files_the_app_expects(monkeypatch, track):
    monkeypatch.setenv("DEMUCS_BACKEND", "modal")
    monkeypatch.setattr(engine, "_separate_on_modal", fake_gpu_ok)
    calls = []
    monkeypatch.setattr(engine, "_separate_locally", lambda tp: calls.append("cpu"))

    stems = engine.split_stems(track)

    assert calls == [], "the CPU path must not run when the GPU succeeds"
    assert set(stems) == {"bass", "drums", "other", "vocals"}
    for name, path in stems.items():
        assert path == track.stems_dir / f"{name}.wav"
        assert path.read_bytes() == b"RIFF" + name.encode()


def test_gpu_failure_falls_back_to_cpu(monkeypatch, track, capsys):
    monkeypatch.setenv("DEMUCS_BACKEND", "modal")

    def gpu_down(audio, ext):
        raise ConnectionError("modal unreachable")

    def cpu(tp):
        for name in ("bass", "drums", "other", "vocals"):
            (tp.stems_dir / f"{name}.wav").write_bytes(b"cpu")

    monkeypatch.setattr(engine, "_separate_on_modal", gpu_down)
    monkeypatch.setattr(engine, "_separate_locally", cpu)

    stems = engine.split_stems(track)

    assert stems["vocals"].read_bytes() == b"cpu"
    assert "falling back" in capsys.readouterr().err.lower()


def test_gpu_result_missing_a_stem_falls_back_to_cpu(monkeypatch, track):
    monkeypatch.setenv("DEMUCS_BACKEND", "modal")
    monkeypatch.setattr(engine, "_separate_on_modal", lambda a, e: {"vocals": b"x"})
    used = []

    def cpu(tp):
        used.append(1)
        for name in ("bass", "drums", "other", "vocals"):
            (tp.stems_dir / f"{name}.wav").write_bytes(b"cpu")

    monkeypatch.setattr(engine, "_separate_locally", cpu)
    engine.split_stems(track)
    assert used == [1]


def test_local_backend_never_touches_modal(monkeypatch, track):
    monkeypatch.delenv("DEMUCS_BACKEND", raising=False)

    def never(audio, ext):
        raise AssertionError("modal must not be called")

    def cpu(tp):
        for name in ("bass", "drums", "other", "vocals"):
            (tp.stems_dir / f"{name}.wav").write_bytes(b"cpu")

    monkeypatch.setattr(engine, "_separate_on_modal", never)
    monkeypatch.setattr(engine, "_separate_locally", cpu)
    assert set(engine.split_stems(track)) == {"bass", "drums", "other", "vocals"}


def test_modal_app_definition_imports_without_an_account():
    """The GPU app file must at least be valid: decorators build, names match."""
    import importlib
    mod = importlib.import_module("modal_app.demucs_gpu")
    assert mod.APP_NAME == engine.MODAL_APP_NAME
    assert mod.FUNCTION_NAME == engine.MODAL_FUNCTION_NAME
    assert hasattr(mod, "separate")
