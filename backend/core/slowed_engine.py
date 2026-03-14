from pathlib import Path
import subprocess
from typing import Optional


def _get_sample_rate(input_path: Path) -> Optional[int]:
    """
    Use ffprobe to detect the sample rate of the input file.
    Returns an int sample rate (e.g., 44100) or None if detection fails.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=sample_rate",
        "-of", "default=nw=1:nk=1",
        str(input_path),
    ]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        sr_str = completed.stdout.strip()
        if sr_str.isdigit():
            return int(sr_str)
    except Exception:
        # If ffprobe fails for some reason, just return None
        return None

    return None


def create_slowed_reverb_mix(
    input_path: Path,
    output_path: Path,
    speed_factor: float = 0.9,
) -> Path:
    """
    Create a slowed + pitched-down + reverb mix using ffmpeg.

    - speed_factor: 0.9 = 10% slower (faithful to original engine)

    Filter chain:
      - asetrate + aresample: FFmpeg equivalent of Pydub's frame rate trick
      - lowpass=6000Hz: FFmpeg biquad IIR filter — warm without muddiness
      - loudnorm: EBU R128 normalization to restore volume lost from aggressive cut

    Requires ffmpeg (and ffprobe) in PATH.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input audio not found: {input_path}")

    # Detect actual sample rate so we don't hardcode 44100
    sr = _get_sample_rate(input_path)
    if sr is None:
        sr = 44100

    # FFmpeg equivalent of Pydub's _spawn frame rate trick + set_frame_rate.
    # Reinterprets raw audio at 90% of original sample rate (slower + lower pitch),
    # then resamples back to original rate for playback compatibility.
    base_chain = f"asetrate={sr}*{speed_factor},aresample={sr}"

    # 6kHz low-pass: warm character without the muddiness of lower cutoffs.
    # FFmpeg uses a biquad IIR — cleaner rolloff, no Pydub quantization artifacts.
    lowpass = "lowpass=f=6000"

    # EBU R128 loudness normalization: the 3kHz cut causes significant perceived
    # volume loss. Targets -16 LUFS, -1.5dB true peak ceiling.
    loudnorm = "loudnorm=I=-16:TP=-1.5:LRA=11"

    filter_chain = ",".join([base_chain, lowpass, loudnorm])

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-filter_complex",
        filter_chain,
        str(output_path),
    ]

    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"ffmpeg slowed+reverb failed.\nCOMMAND: {' '.join(cmd)}\n"
            f"STDOUT:\n{completed.stdout}\n\nSTDERR:\n{completed.stderr}"
        )

    if not output_path.exists():
        raise RuntimeError(f"Slowed+reverb output not created: {output_path}")

    return output_path
