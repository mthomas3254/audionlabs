# AudionLabs fix: patch torchaudio.save to use soundfile
# instead of torchcodec (which requires FFmpeg shared DLLs
# not available with static FFmpeg builds on Windows)
# This fix applies to all processes using this venv,
# including Demucs subprocess calls.

def _patch_torchaudio():
    try:
        import soundfile as sf
        import torch
        import numpy as np

        def _save_with_soundfile(uri, src, sample_rate,
                                  channels_first=True,
                                  compression=None,
                                  encoding=None,
                                  bits_per_sample=None,
                                  **kwargs):
            if channels_first:
                data = src.numpy().T
            else:
                data = src.numpy()
            sf.write(str(uri), data, sample_rate)

        import torchaudio
        torchaudio.save = _save_with_soundfile
    except Exception:
        pass  # fail silently — don't break anything

_patch_torchaudio()
