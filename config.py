"""Configuration for Intelligent Document Q&A via Gemini File Search (Developer API)."""
import os
import logging

logger = logging.getLogger(__name__)


class Config:
    """Application configuration."""

    # Gemini Developer API — File Search is not available on Vertex in this SDK path.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Reuse an existing store by full resource name, e.g. fileSearchStores/abc123
    FILE_SEARCH_STORE_NAME = os.getenv("FILE_SEARCH_STORE_NAME", "").strip()

    # When creating or discovering a store, this display name is used.
    # Must match gcs-sync-job/sync_job.py default so service + job share one store.
    FILE_SEARCH_STORE_DISPLAY_NAME = os.getenv(
        "FILE_SEARCH_STORE_DISPLAY_NAME", "Gemini File Search demo"
    )

    # Persist discovered store name locally (gitignored) for dev restarts.
    STORE_STATE_FILE = os.getenv("FILE_SEARCH_STORE_STATE_FILE", ".file_search_store.json")

    ALLOWED_EXTENSIONS = frozenset(
        {
            "pdf",
            "docx",
            "doc",
            "txt",
            "md",
            "csv",
        }
    )


def api_configured() -> bool:
    return bool(Config.GEMINI_API_KEY)
