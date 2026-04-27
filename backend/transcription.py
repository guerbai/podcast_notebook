from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from backend.config import MODELS_DIR, TRANSCRIPTS_DIR


_MODEL_CACHE: dict[str, Any] = {}
_REQUIRED_MODEL_FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")


def sanitize_filename(value: str) -> str:
    slug = re.sub(r"[^\w\s-]+", "", value, flags=re.UNICODE).strip()
    slug = re.sub(r"[-\s]+", "-", slug, flags=re.UNICODE)
    return slug or "transcript"


def transcript_output_path(title: str) -> Path:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    return TRANSCRIPTS_DIR / f"{sanitize_filename(title)}.txt"


def _audio_duration_seconds(audio_path: str | Path) -> float:
    import av

    with av.open(str(audio_path)) as container:
        if container.duration is None:
            return 0.0
        return float(container.duration / 1_000_000)


def _configure_hf_environment() -> None:
    hf_home = MODELS_DIR / "hf-home"
    hub_cache = hf_home / "hub"
    hf_home.mkdir(parents=True, exist_ok=True)
    hub_cache.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hub_cache)
    os.environ["HF_HUB_DISABLE_XET"] = "1"


def _model_repo_dir(model_size: str) -> Path:
    return MODELS_DIR / f"models--Systran--faster-whisper-{model_size}"


def _snapshot_is_complete(model_size: str) -> bool:
    repo_dir = _model_repo_dir(model_size)
    ref_path = repo_dir / "refs" / "main"
    if not ref_path.exists():
        return False
    snapshot_id = ref_path.read_text(encoding="utf-8").strip()
    if not snapshot_id:
        return False
    snapshot_dir = repo_dir / "snapshots" / snapshot_id
    return all((snapshot_dir / name).exists() for name in _REQUIRED_MODEL_FILES)


def _clear_broken_snapshot(model_size: str) -> None:
    repo_dir = _model_repo_dir(model_size)
    if repo_dir.exists():
        shutil.rmtree(repo_dir)


def _load_model(model_size: str):
    from faster_whisper import WhisperModel

    if model_size not in _MODEL_CACHE:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        _configure_hf_environment()
        if _model_repo_dir(model_size).exists() and not _snapshot_is_complete(model_size):
            _clear_broken_snapshot(model_size)
        _MODEL_CACHE[model_size] = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=str(MODELS_DIR),
        )
    return _MODEL_CACHE[model_size]


def transcribe_audio(
    audio_path: str | Path,
    title: str,
    progress_callback=None,
    model_size: str = "base",
) -> Path:
    output_path = transcript_output_path(title)
    model = _load_model(model_size)
    total_seconds = _audio_duration_seconds(audio_path)
    segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        vad_filter=True,
        language=None,
    )

    transcript_lines: list[str] = []
    if progress_callback:
        progress_callback(0.0, total_seconds, f"model={model_size}, language={info.language}")
    for segment in segments:
        transcript_lines.append(segment.text.strip())
        if progress_callback:
            progress_callback(float(segment.end), total_seconds, segment.text.strip())

    output_path.write_text("\n\n".join(line for line in transcript_lines if line), encoding="utf-8")
    return output_path
