"""Runtime configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # HTTP server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # LLM provider
    llm_provider: str = "ollama"  # ollama | gemini
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    llm_temperature: float = 0.2
    # Qwen3 "thinking" is high quality but slow (~minutes/step). Default ON for
    # best RTL quality. Set False to append `/no_think` for faster, shallower runs.
    ollama_think: bool = True
    # Ollama defaults to a tiny ~4k context; with thinking ON the <think> block
    # alone can overflow it and truncate the actual code. Give it real headroom.
    # 32k fits qwen3.5:9b reasoning + RTL (offloads some KV cache to RAM on 8GB).
    ollama_num_ctx: int = 32768
    ollama_num_predict: int = -1  # generate until EOS, bounded by num_ctx
    google_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"

    # Agent behaviour
    max_retries: int = 3

    # Research / RAG: crawl reference designs from the web (crawl4ai) and retrieve
    # the most relevant snippets (sentence-transformers + FAISS) into the generator.
    use_web: bool = True
    use_rag: bool = True
    rag_index_dir: str | None = None
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # GitHub: pull real .v/.sv files from top repos (the highest-quality source).
    github_token: str | None = None  # optional, raises API rate limits
    github_max_repos: int = 10
    github_max_files: int = 10
    # Web / papers (filtered, junk domains excluded).
    web_max_results: int = 10
    web_crawl_limit: int = 10
    web_timeout_sec: int = 25
    rag_top_k: int = 6
    rag_chunk_chars: int = 1400
    reference_char_budget: int = 6000

    # EDA tools
    iverilog_bin: str = "iverilog"
    vvp_bin: str = "vvp"
    sim_timeout_sec: int = 120
    run_harden: bool = True
    librelane_cmd: str = "librelane"
    harden_timeout_sec: int = 3600
    default_pdk: str = "sky130A"
    default_stdcell: str = "sky130_fd_sc_hd"

    # Storage — local working cache for generated files.
    workspace_root: str = "./.workspaces"

    # Durable persistence (optional, config-driven). When DATABASE_URL is set the
    # backend mirrors task state + logs to Postgres; when S3 creds are set it
    # mirrors generated files to S3/MinIO object storage. Unset => local-only.
    database_url: str | None = None
    # S3 / MinIO object storage
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "chiporchestra"
    s3_region: str = "us-east-1"

    @property
    def persistence_enabled(self) -> bool:
        return bool(self.database_url)

    @property
    def object_storage_enabled(self) -> bool:
        return bool(self.s3_endpoint_url and self.s3_access_key and self.s3_secret_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def workspace_path(self) -> Path:
        path = Path(self.workspace_root).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
