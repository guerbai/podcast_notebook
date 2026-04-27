from pathlib import Path


def test_requirements_file_exists():
    assert Path("requirements.txt").exists()
