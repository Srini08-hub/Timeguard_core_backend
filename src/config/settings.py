from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    DATABASE_URI: str
    SYNC_DATABASE_URI: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REFRESH_TOKEN: str
    GMAIL_POLL_MAILBOX_ADDRESS: str
    GMAIL_POLL_INTERVAL_SECONDS: int = 120
    GROQ_API_KEY_1: str
    GROQ_API_KEY_2: str
    GROQ_API_KEY_3: str
    GOOGLE_API_KEY: str
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_QUEUE_NAME: str = "timeguard_queue"
    ATTACHMENT_STORAGE_DIR: Path = BASE_DIR / "attachments"
    ATTACHMENT_BASE_URL: str = "http://localhost:8002/attachments"
    GCS_BUCKET_NAME: str | None = None
    GCS_ATTACHMENT_PREFIX: str = "timeguard/attachments"
    LOCAL_ATTACHMENT_TMP_DIR: Path = Path("/tmp/timeguard-attachments")
    LLAMA_CLOUD_API_KEY: str
    LANGSMITH_API_KEY: str
    LANGSMITH_TRACING: bool = False
    LANGSMITH_PROJECT: str = "Default"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
