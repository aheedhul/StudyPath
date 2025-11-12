import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StudyPath API"
    database_url: str = "sqlite+aiosqlite:///./studypath.db"
    data_dir: Path = Path("./data")
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-70b-versatile"
    assessment_question_count: int = 6
    assessment_question_chapter_window: int = 3
    learning_phase_ratio: float = 0.7
    testing_phase_ratio: float = 0.3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_prefix="STUDYPATH_")

    def model_post_init(self, __context: dict[str, object]) -> None:
        if not self.groq_api_key:
            fallback = os.getenv("GROQ_API_KEY")
            if fallback:
                object.__setattr__(self, "groq_api_key", fallback)


settings = Settings()
