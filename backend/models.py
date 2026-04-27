from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TaskRecord:
    id: int
    podcast_title: str
    rss_url: str
    episode_title: str
    episode_guid: str | None
    audio_url: str
    shownotes: str
    summarize: str
    status: str
    progress_stage: str
    progress_percent: float
    audio_file_path: str | None
    output_txt_path: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
