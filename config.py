import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        # ── General ──────────────────────────────────────────────
        cache_ttl_hours:   int   = 12
        max_retries:       int   = 5

        # ── Twitter ──────────────────────────────────────────────
        auth_token:        str   = ""
        ct0:               str   = ""
        max_per_page:      int   = 20
        rotate_every:      int   = 12
        page_delay:        float = 0.25
        rotate_delay:      float = 0.8
        qid_cache_hours:   int   = 6
        max_empty_pages:   int   = 2
        checkpoint_dir:    str   = "checkpoints"
        token_pool_size:   int   = 6
        parallel_windows:  int   = 3
        backoff_base:      float = 1.5

        class Config:
            env_file = ".env"

    settings = Settings()

except ImportError:
    class _S:
        cache_ttl_hours  = 12
        max_retries      = 5
        auth_token       = os.getenv("AUTH_TOKEN", "")
        ct0              = os.getenv("CT0", "")
        max_per_page     = 20
        rotate_every     = 12
        page_delay       = 0.25
        rotate_delay     = 0.8
        qid_cache_hours  = 6
        max_empty_pages  = 2
        checkpoint_dir   = "checkpoints"
        token_pool_size  = 6
        parallel_windows = 3
        backoff_base     = 1.5
    settings = _S()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
CACHE_DIR      = BASE_DIR / "cache"
CHECKPOINT_DIR = BASE_DIR / settings.checkpoint_dir
QID_CACHE_FILE = CACHE_DIR / "_qids.json"

CACHE_DIR.mkdir(exist_ok=True)
CHECKPOINT_DIR.mkdir(exist_ok=True)

# ── Twitter bearer ─────────────────────────────────────────────────────────────
TWITTER_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)