import os
import sys
import types
from pathlib import Path

import backend.transcription as transcription
from backend.transcription import transcript_output_path


def test_transcript_output_path_uses_txt_suffix():
    path = transcript_output_path("vol.1385 从小龙虾跑路到Codex")
    assert str(path).endswith(".txt")


def test_load_model_clears_broken_snapshot_and_uses_repo_local_hf_cache(tmp_path, monkeypatch):
    repo_dir = tmp_path / "models--Systran--faster-whisper-base"
    snapshot_dir = repo_dir / "snapshots" / "commit123"
    snapshot_dir.mkdir(parents=True)
    (repo_dir / "refs").mkdir(parents=True)
    (repo_dir / "refs" / "main").write_text("commit123", encoding="utf-8")
    (repo_dir / "blobs").mkdir(parents=True)
    (snapshot_dir / "config.json").write_text("{}", encoding="utf-8")
    (snapshot_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
    (snapshot_dir / "vocabulary.txt").write_text("stub", encoding="utf-8")
    (snapshot_dir / "model.bin").symlink_to(Path("../../blobs/missing-model"))

    calls: dict[str, object] = {}

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            calls["args"] = args
            calls["kwargs"] = kwargs

    monkeypatch.setattr(transcription, "MODELS_DIR", tmp_path)
    transcription._MODEL_CACHE.clear()
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.delenv("HF_HUB_DISABLE_XET", raising=False)

    model = transcription._load_model("base")

    assert isinstance(model, FakeWhisperModel)
    assert calls["args"] == ("base",)
    assert calls["kwargs"]["download_root"] == str(tmp_path)
    assert os.environ["HF_HOME"] == str(tmp_path / "hf-home")
    assert os.environ["HUGGINGFACE_HUB_CACHE"] == str(tmp_path / "hf-home" / "hub")
    assert os.environ["HF_HUB_DISABLE_XET"] == "1"
    assert not repo_dir.exists()
