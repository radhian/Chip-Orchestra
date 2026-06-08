"""Web research + RAG over reference designs (GarudaChip-style).

Two high-signal sources, like GarudaChip's `agent_web`:
  1. **GitHub** — search top Verilog repos and pull their raw ``.v``/``.sv`` files
     (pure HDL, no HTML/boilerplate). This is the best reference material.
  2. **Web / papers** — a filtered web search (junk domains like scribd excluded),
     crawled with crawl4ai, from which only fenced Verilog code blocks are kept.

Everything is then filtered to chunks that actually look like Verilog, embedded
(sentence-transformers), indexed (FAISS), and the top matches are returned to
ground the generator. Every stage degrades gracefully.
"""

from __future__ import annotations

import asyncio
import re

import httpx

from .. import control
from ..config import get_settings

# Domains that pollute results with cookie banners / nav instead of HDL.
JUNK_DOMAINS = (
    "scribd.com", "slideshare.net", "coursehero.com", "studocu.com", "docsity.com",
    "academia.edu", "quizlet.com", "pinterest.", "facebook.", "youtube.com",
    "linkedin.com", "amazon.", "researchgate.net",
)

VERILOG_TOKENS = (
    "module", "endmodule", "always", "assign", "reg ", "wire ",
    "input ", "output ", "posedge", "negedge", "begin", "parameter",
)

# Research depth presets (GitHub files, web pages crawled, RAG chunks returned).
RESEARCH_DEPTH = {
    "SMALL": {"github": 3, "web": 3, "top_k": 3},
    "MEDIUM": {"github": 6, "web": 6, "top_k": 5},
    "DEEP": {"github": 10, "web": 10, "top_k": 6},
}

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(get_settings().embedding_model)
    return _embedder


def _looks_verilog(text: str) -> bool:
    low = text.lower()
    if "module" not in low:
        return False
    return sum(tok in low for tok in VERILOG_TOKENS) >= 3


# --- GitHub (raw .v/.sv files from top repos) -------------------------------
def _gh_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "chip-orchestra"}
    token = get_settings().github_token
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_raw_urls(query: str, max_repos: int, max_files: int) -> list[str]:
    """Find raw URLs of Verilog files in the most relevant/starred repos."""
    urls: list[str] = []
    try:
        resp = httpx.get(
            "https://api.github.com/search/repositories",
            params={"q": f"{query} verilog", "sort": "stars", "per_page": max_repos},
            headers=_gh_headers(), timeout=20,
        )
        repos = resp.json().get("items", []) if resp.status_code == 200 else []
    except Exception:  # noqa: BLE001
        return urls

    for repo in repos:
        if len(urls) >= max_files:
            break
        full = repo.get("full_name")
        branch = repo.get("default_branch", "master")
        if not full:
            continue
        try:
            tree = httpx.get(
                f"https://api.github.com/repos/{full}/git/trees/{branch}",
                params={"recursive": "1"}, headers=_gh_headers(), timeout=20,
            ).json().get("tree", [])
        except Exception:  # noqa: BLE001
            continue
        v_files = [
            n["path"] for n in tree
            if n.get("type") == "blob" and n.get("path", "").endswith((".v", ".sv"))
            and "tb" not in n["path"].lower() and "test" not in n["path"].lower()
        ][:2]  # up to 2 files per repo to keep variety
        for path in v_files:
            urls.append(f"https://raw.githubusercontent.com/{full}/{branch}/{path}")
            if len(urls) >= max_files:
                break
    return urls


def _fetch_raw(url: str, timeout: int) -> str:
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        return resp.text if resp.status_code == 200 else ""
    except Exception:  # noqa: BLE001
        return ""


# --- Web / papers (filtered) ------------------------------------------------
def web_search(query: str, max_results: int) -> list[str]:
    try:
        from ddgs import DDGS
    except ImportError:  # older package name
        from duckduckgo_search import DDGS  # type: ignore

    urls: list[str] = []

    def _collect(q: str) -> None:
        try:
            with DDGS() as ddgs:
                for row in ddgs.text(q, max_results=max_results * 3):
                    url = row.get("href") or row.get("url") or ""
                    if not url or any(j in url for j in JUNK_DOMAINS):
                        continue
                    if url not in urls:
                        urls.append(url)
                    if len(urls) >= max_results:
                        return
        except Exception:  # noqa: BLE001
            pass

    _collect(f"{query} verilog module implementation example")
    if len(urls) < max_results:
        _collect(f"{query} verilog OR systemverilog rtl design paper")
    return urls[:max_results]


def _markdown_of(result) -> str:
    md = getattr(result, "markdown", "") or ""
    if not isinstance(md, str):
        md = getattr(md, "raw_markdown", "") or str(md)
    return md


async def _crawl_async(urls: list[str], limit: int, timeout: int) -> list[tuple[str, str]]:
    from crawl4ai import AsyncWebCrawler

    sem = asyncio.Semaphore(4)
    docs: list[tuple[str, str]] = []

    async with AsyncWebCrawler(verbose=False) as crawler:
        async def _one(url: str) -> None:
            async with sem:
                try:
                    res = await asyncio.wait_for(crawler.arun(url=url), timeout=timeout)
                    text = _markdown_of(res)
                    if text and len(text) > 200:
                        docs.append((url, text))
                except Exception:  # noqa: BLE001
                    return

        await asyncio.gather(*(_one(u) for u in urls[:limit]))
    return docs


def crawl(urls: list[str], limit: int, timeout: int) -> list[tuple[str, str]]:
    if not urls:
        return []
    try:
        return asyncio.run(_crawl_async(urls, limit, timeout))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_crawl_async(urls, limit, timeout))
        finally:
            loop.close()


# --- chunking + RAG ---------------------------------------------------------
def _code_blocks(text: str) -> list[str]:
    """Verilog code fences from a web page (drops nav/cookie prose)."""
    blocks = []
    for match in re.finditer(r"```[a-zA-Z0-9_+-]*\n(.*?)```", text, re.DOTALL):
        code = match.group(1).strip()
        if _looks_verilog(code):
            blocks.append(code)
    return blocks


def _chunk_code(code: str, size: int) -> list[str]:
    """Chunk a raw Verilog file, preferring one chunk per module."""
    from .llm import split_verilog_modules

    modules = split_verilog_modules(code)
    if modules:
        return [c[: size * 2] for c in modules.values()]
    return [code[: size * 2]] if _looks_verilog(code) else []


def rag_select(brief: str, chunks: list[str], top_k: int) -> list[str]:
    if not chunks:
        return []
    try:
        import faiss
        import numpy as np

        embedder = _get_embedder()
        vectors = np.asarray(embedder.encode(chunks, normalize_embeddings=True), dtype="float32")
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        query = np.asarray(embedder.encode([brief], normalize_embeddings=True), dtype="float32")
        _scores, ids = index.search(query, min(top_k, len(chunks)))
        return [chunks[i] for i in ids[0] if 0 <= i < len(chunks)]
    except Exception:  # noqa: BLE001
        return chunks[:top_k]


def gather_reference(brief: str, depth: str = "MEDIUM", task_id: str | None = None) -> tuple[str, list[str]]:
    """GitHub raw .v + filtered web code → Verilog-only chunks → RAG select.

    ``depth`` (SMALL/MEDIUM/DEEP) scales how many GitHub files + web pages are
    pulled (3+3, 6+6, 10+10) and how many chunks are returned. ``task_id`` enables
    stop/cancel checks between sources.
    """
    settings = get_settings()
    preset = RESEARCH_DEPTH.get((depth or "MEDIUM").upper(), RESEARCH_DEPTH["MEDIUM"])
    n_github, n_web, top_k = preset["github"], preset["web"], preset["top_k"]
    chunks: list[str] = []
    sources: list[str] = []

    def _check() -> None:
        if task_id:
            control.checkpoint(task_id)

    if settings.use_web:
        # 1) GitHub raw Verilog files (highest quality).
        for url in github_raw_urls(brief, n_github, n_github):
            _check()
            raw = _fetch_raw(url, settings.web_timeout_sec)
            file_chunks = _chunk_code(raw, settings.rag_chunk_chars)
            if file_chunks:
                chunks.extend(file_chunks)
                sources.append(url)

        # 2) Web / papers — keep only Verilog code blocks.
        _check()
        for url, md in crawl(web_search(brief, n_web), n_web, settings.web_timeout_sec):
            blocks = _code_blocks(md)
            if blocks:
                chunks.extend(b[: settings.rag_chunk_chars * 2] for b in blocks)
                sources.append(url)

    # Final guard: only Verilog-looking chunks ever reach the generator.
    chunks = [c for c in chunks if _looks_verilog(c)]
    if not chunks:
        return "", sources

    selected = rag_select(brief, chunks, top_k) if settings.use_rag else chunks[:top_k]
    reference = "\n\n---\n\n".join(selected)[: settings.reference_char_budget]
    return reference, sources
