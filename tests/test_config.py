from pathlib import Path

from backend.config import load_project_config


def test_requirements_file_exists():
    assert Path("requirements.txt").exists()


def test_load_project_config_reads_yaml_llm_and_podcast_names(tmp_path):
    config_path = tmp_path / "podcast_notebook.yaml"
    config_path.write_text(
        """
llm:
  api_key: test-key
  base_url: https://llm.example.com/v1
  model: test-model
  timeout_seconds: 12

subscriptions:
  podcasts:
    - 商业就是这样
    - 半拿铁 | 商业沉浮录
""".strip(),
        encoding="utf-8",
    )

    config = load_project_config(config_path)

    assert config.llm.api_key == "test-key"
    assert config.llm.base_url == "https://llm.example.com/v1"
    assert config.llm.model == "test-model"
    assert config.llm.timeout_seconds == 12
    assert config.subscriptions.podcasts == ["商业就是这样", "半拿铁 | 商业沉浮录"]


def test_load_project_config_ignores_blank_podcast_names(tmp_path):
    config_path = tmp_path / "podcast_notebook.yaml"
    config_path.write_text(
        """
subscriptions:
  podcasts:
    - " 商业就是这样 "
    - ""
    - "   "
""".strip(),
        encoding="utf-8",
    )

    config = load_project_config(config_path)

    assert config.subscriptions.podcasts == ["商业就是这样"]
