"""Long-running work must run as background jobs.

Cloudflare closes any request that takes longer than 100 seconds and shows the
visitor a 524. Demucs and Whisper on Railway's CPU take minutes, so the upload
returns a job id at once and the page polls /jobs/{id}.
"""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import jobs as jobs_module
from backend.main import app

MP3 = ("clip.mp3", b"ID3\x03\x00\x00\x00\x00\x00\x00fake-mp3-bytes", "audio/mpeg")


@pytest.fixture()
def client():
    return TestClient(app)


def wait_for(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish in time")


def fake_split(track_paths):
    out = {}
    for name in ("bass", "drums", "other", "vocals"):
        p = track_paths.stems_dir / f"{name}.wav"
        p.write_bytes(b"RIFF")
        out[name] = p
    return out


# ---- job store ----

def test_job_store_runs_work_and_reports_stages():
    store = jobs_module.JobStore(workers=1)
    seen = []

    def work(set_stage):
        set_stage("Separating stems")
        seen.append("ran")
        return {"ok": True}

    job = store.submit("test", work)
    # the worker thread may already have picked it up
    assert job.status in ("queued", "running", "done")
    deadline = time.time() + 3
    while store.get(job.id).status != "done" and time.time() < deadline:
        time.sleep(0.01)
    done = store.get(job.id)
    assert done.status == "done" and done.result == {"ok": True} and seen == ["ran"]


def test_job_store_records_errors_without_leaking_tracebacks():
    store = jobs_module.JobStore(workers=1)

    def work(set_stage):
        raise RuntimeError("Stem separation failed.")

    job = store.submit("test", work)
    deadline = time.time() + 3
    while store.get(job.id).status != "error" and time.time() < deadline:
        time.sleep(0.01)
    failed = store.get(job.id)
    assert failed.status == "error"
    assert failed.error == "Stem separation failed."
    assert "Traceback" not in failed.public()["error"]


def test_finished_jobs_expire(monkeypatch):
    store = jobs_module.JobStore(workers=1)
    job = store.submit("test", lambda set_stage: {"x": 1})
    deadline = time.time() + 3
    while store.get(job.id).status != "done" and time.time() < deadline:
        time.sleep(0.01)
    store.get(job.id).updated -= jobs_module.MAX_AGE_SECONDS + 1
    store.submit("test", lambda set_stage: {"y": 2})   # triggers expiry
    assert store.get(job.id) is None


# ---- /process_audio ----

def test_process_audio_returns_a_job_at_once_and_finishes_in_the_background(client, monkeypatch):
    import backend.core.demucs_engine as engine
    monkeypatch.setattr(engine, "split_stems", fake_split)

    started = time.time()
    res = client.post("/process_audio", files={"file": MP3},
                      data={"split_stems_flag": "true", "slowed_reverb_flag": "false"})
    assert res.status_code == 202, res.text
    assert time.time() - started < 2
    job_id = res.json()["job_id"]

    job = wait_for(client, job_id)
    assert job["status"] == "done", job
    result = job["result"]
    assert set(result["stems"]) == {"bass", "drums", "other", "vocals"}
    assert result["stems"]["vocals"]["download_name"] == "clip_vocals.wav"
    assert result["stems"]["vocals"]["url"].startswith("/media/stems/")
    assert result["slowed_mix"] is None


def test_process_audio_failure_is_reported_through_the_job(client, monkeypatch):
    import backend.core.demucs_engine as engine

    def boom(track_paths):
        raise RuntimeError("Demucs failed.\nCOMMAND: python -m demucs /secret/path\nSTDERR: kaboom")

    monkeypatch.setattr(engine, "split_stems", boom)
    res = client.post("/process_audio", files={"file": MP3},
                      data={"split_stems_flag": "true", "slowed_reverb_flag": "false"})
    assert res.status_code == 202
    job = wait_for(client, res.json()["job_id"])
    assert job["status"] == "error"
    assert "Stem separation failed" in job["error"]
    assert "/secret/path" not in job["error"]


def test_process_audio_still_validates_before_queueing(client):
    res = client.post("/process_audio", files={"file": ("x.flac", b"x", "audio/flac")},
                      data={"split_stems_flag": "true"})
    assert res.status_code == 400
    res = client.post("/process_audio", files={"file": MP3},
                      data={"split_stems_flag": "false", "slowed_reverb_flag": "false"})
    assert res.status_code == 400


def test_unknown_job_is_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404


def test_job_status_response_shape(client, monkeypatch):
    import backend.core.demucs_engine as engine
    monkeypatch.setattr(engine, "split_stems", fake_split)
    res = client.post("/process_audio", files={"file": MP3},
                      data={"split_stems_flag": "true", "slowed_reverb_flag": "false"})
    job = client.get(f"/jobs/{res.json()['job_id']}").json()
    for key in ("job_id", "status", "stage", "result", "error"):
        assert key in job
    wait_for(client, job["job_id"])


# ---- /transcribe ----

def test_transcribe_runs_as_a_job(client, monkeypatch):
    import backend.core.transcribe_engine as engine

    def fake_transcribe(path, key):
        assert Path(path).exists()
        return {"transcript": "hello world", "srt": "1\n00:00:00,000 --> 00:00:01,000\nhello\n",
                "summary": "", "topics": [], "chapters": []}

    monkeypatch.setattr(engine, "transcribe_audio", fake_transcribe)
    res = client.post("/transcribe", files={"file": MP3})
    assert res.status_code == 202, res.text
    job = wait_for(client, res.json()["job_id"])
    assert job["status"] == "done"
    assert job["result"]["transcript"] == "hello world"


def test_transcribe_rejects_missing_input_immediately(client):
    assert client.post("/transcribe").status_code == 400
