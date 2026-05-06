from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "podcast_notebook.yaml"
DATA_DIR = ROOT_DIR / "data"
DB_DIR = DATA_DIR / "db"
DOWNLOADS_DIR = DATA_DIR / "downloads"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
SUMMARIES_DIR = DATA_DIR / "summaries"
SHOWNOTES_DIR = DATA_DIR / "shownotes"
MODELS_DIR = DATA_DIR / "models"
DB_PATH = DB_DIR / "podcast_notebook.db"
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_LLM_TIMEOUT_SECONDS = 60.0


class ConfigError(RuntimeError):
    """Raised when the project YAML config cannot be read safely."""


@dataclass(slots=True)
class LLMConfig:
    api_key: str = ""
    base_url: str = DEFAULT_LLM_BASE_URL
    model: str = DEFAULT_LLM_MODEL
    timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS


@dataclass(slots=True)
class SubscriptionsConfig:
    podcasts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    subscriptions: SubscriptionsConfig = field(default_factory=SubscriptionsConfig)


def project_config_path() -> Path:
    override = os.environ.get("PODCAST_NOTEBOOK_CONFIG", "").strip()
    return Path(override) if override else CONFIG_PATH


def load_project_config(config_path: str | Path | None = None) -> ProjectConfig:
    path = Path(config_path) if config_path is not None else project_config_path()
    if not path.exists():
        return ProjectConfig()

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML config: {path}") from exc
    except OSError as exc:
        raise ConfigError(f"Unable to read config: {path}") from exc

    if not isinstance(payload, dict):
        raise ConfigError("Project config must be a YAML mapping")

    return ProjectConfig(
        llm=_load_llm_config(payload.get("llm")),
        subscriptions=_load_subscriptions_config(payload.get("subscriptions")),
    )


def _load_llm_config(value: Any) -> LLMConfig:
    if value is None:
        return LLMConfig()
    if not isinstance(value, dict):
        raise ConfigError("llm config must be a mapping")
    return LLMConfig(
        api_key=str(value.get("api_key", "") or "").strip(),
        base_url=str(value.get("base_url", DEFAULT_LLM_BASE_URL) or DEFAULT_LLM_BASE_URL).strip(),
        model=str(value.get("model", DEFAULT_LLM_MODEL) or DEFAULT_LLM_MODEL).strip(),
        timeout_seconds=float(value.get("timeout_seconds", DEFAULT_LLM_TIMEOUT_SECONDS)),
    )


def _load_subscriptions_config(value: Any) -> SubscriptionsConfig:
    if value is None:
        return SubscriptionsConfig()
    if not isinstance(value, dict):
        raise ConfigError("subscriptions config must be a mapping")

    raw_podcasts = value.get("podcasts", [])
    if raw_podcasts is None:
        return SubscriptionsConfig()
    if not isinstance(raw_podcasts, list):
        raise ConfigError("subscriptions.podcasts must be a list")

    podcasts = []
    for item in raw_podcasts:
        if not isinstance(item, str):
            raise ConfigError("subscriptions.podcasts items must be strings")
        name = item.strip()
        if name:
            podcasts.append(name)
    return SubscriptionsConfig(podcasts=podcasts)
