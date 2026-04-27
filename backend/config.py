from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_DIR = DATA_DIR / "db"
DOWNLOADS_DIR = DATA_DIR / "downloads"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
SUMMARIES_DIR = DATA_DIR / "summaries"
SHOWNOTES_DIR = DATA_DIR / "shownotes"
MODELS_DIR = DATA_DIR / "models"
DB_PATH = DB_DIR / "podcast_notebook.db"
