"""Demucs stem separation on a Modal GPU.

Deploy once from an authenticated machine:

    modal deploy modal_app/demucs_gpu.py

Then on Railway set DEMUCS_BACKEND=modal plus MODAL_TOKEN_ID and
MODAL_TOKEN_SECRET (from `modal token new`). backend/core/demucs_engine.py
calls `separate` and falls back to the local CPU path if this is unreachable.

The image bakes the htdemucs weights in at build time, so a cold container
does not download them per song. Costs are billed per second the container
runs; a full song takes roughly 10 to 30 seconds on an A10G.
"""
import modal

APP_NAME = "audionlabs-demucs"
FUNCTION_NAME = "separate"
MODEL = "htdemucs"
STEMS = ("bass", "drums", "other", "vocals")

# torch/torchaudio 2.5.1 avoid the torchcodec save problem (see BLUEPRINT Bug 1).
# The Linux wheels on PyPI include CUDA support.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install("torch==2.5.1", "torchaudio==2.5.1", "demucs==4.0.1", "soundfile")
    .run_commands(
        f"python -c \"from demucs.pretrained import get_model; get_model('{MODEL}')\""
    )
)

app = modal.App(APP_NAME)


@app.function(
    image=image,
    gpu="A10G",
    timeout=600,
    scaledown_window=120,   # stay warm two minutes so back-to-back songs skip the cold start
)
def separate(audio: bytes, ext: str = ".mp3") -> dict:
    """Split one track into four stems. Returns {stem_name: wav_bytes}."""
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    if ext not in (".mp3", ".wav"):
        raise ValueError(f"unsupported extension {ext!r}")

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"input{ext}"
        src.write_bytes(audio)
        out = Path(tmp) / "out"
        cmd = [sys.executable, "-m", "demucs", "-n", MODEL, "-d", "cuda", "-o", str(out), str(src)]
        done = subprocess.run(cmd, capture_output=True, text=True)
        if done.returncode != 0:
            raise RuntimeError(f"demucs failed on GPU:\n{done.stderr[-2000:]}")
        stems_dir = out / MODEL / src.stem
        result = {}
        for name in STEMS:
            path = stems_dir / f"{name}.wav"
            if not path.is_file():
                raise RuntimeError(f"demucs did not produce {name}.wav")
            result[name] = path.read_bytes()
        return result


@app.local_entrypoint()
def smoke(path: str = ""):
    """`modal run modal_app/demucs_gpu.py --path song.mp3` splits one file as a test."""
    from pathlib import Path

    if not path:
        print("pass --path to an mp3 or wav")
        return
    src = Path(path)
    stems = separate.remote(src.read_bytes(), src.suffix.lower())
    for name, data in stems.items():
        target = src.with_name(f"{src.stem}_{name}.wav")
        target.write_bytes(data)
        print(f"wrote {target} ({len(data) // 1024} KB)")
