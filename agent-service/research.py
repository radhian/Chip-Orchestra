"""Autonomous web research for the deep agents — ported from GarudaChip.

Gives every stage agent the ability to FIND INFORMATION ONLINE:

* ``search_web`` tool — two modes picked automatically from the query:
  an ERROR/compiler message → a fix hint with the correct code pattern;
  a design/topic → a KNOWLEDGE digest (what it is, how it's built in RTL).
* ``fetch_reference`` tool — pull ONE more reference on demand (GitHub repo →
  real HDL via the API; paper/web page → crawled text) into ``context/refs/``.
* ``gather_references`` — the PLAN-stage reference hunt: understand the prompt,
  collect GitHub repos + papers/pages into ``context/sources.md``, and clone the
  best-matching repo's HDL into ``context/anchor/`` for the generator to study.

Search backends (in order): a self-hosted SearXNG metasearch instance
(``SEARXNG_URL``), the DuckDuckGo library (``ddgs``, no API key), the GitHub
API (optionally with ``GITHUB_TOKEN``), and googlesearch as a last resort.
Crawling uses crawl4ai when installed, else a plain-requests HTML→text
fallback so the docker image stays light.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List

from langchain_core.documents import Document
from langchain_core.tools import tool

from llm import get_chat_model

logger = logging.getLogger("research")

HDL_SET = {"Verilog", "SystemVerilog", "VHDL"}


def clean_llm_output(text: str) -> str:
    if not text:
        return ""
    stripped = re.sub(r"<think>.*?</think>", "", text,
                      flags=re.DOTALL | re.IGNORECASE).strip()
    return stripped or text.strip()


# --------------------------------------------------------------------------- #
# Keyword distillation
# --------------------------------------------------------------------------- #
# Filler words that hurt a GitHub repo search — repo search matches names/topics,
# not prose, so "riscv 8-bit like picorv using fixed point" must become "riscv picorv".
_SEARCH_STOP = {
    "a", "an", "the", "of", "for", "and", "to", "in", "on", "with", "using", "like",
    "that", "this", "my", "your", "please", "make", "build", "create", "design",
    "designs", "implement", "implementation", "module", "modules", "support", "based",
    "is", "it", "bit", "bits", "fixed", "point", "simple", "small", "tiny", "basic",
    "want", "need", "generate", "verilog", "vhdl", "systemverilog", "hdl", "chip",
}

# Generic CPU-STRUCTURE words. They describe a ROLE, not the project — a DISTINCTIVE
# proper-noun (a project NAME like 'fazyrv', 'picorv', 'ibex') must outrank them.
_GENERIC_HDL = {
    "riscv", "risc", "cpu", "core", "processor", "microprocessor", "soc", "system",
    "alu", "regfile", "register", "decoder", "decode", "encoder", "controller", "control",
    "pipeline", "pipelined", "datapath", "arithmetic", "integer", "adder", "subtractor",
    "mux", "fsm", "unit", "design", "logic", "block", "engine", "machine",
}


def _hdl_keywords(text: str, n: int = 4) -> List[str]:
    """Distill a request into the few salient search keywords, DISTINCTIVE NAME
    FIRST. The project name ('fazyrv', 'picorv') is the strongest repo-search
    signal, so it leads, ahead of arch tokens (rv32i), generic structure words
    (riscv/cpu/alu), and width ('8bit')."""
    low = (text or "").lower()
    rv: List[str] = []
    for m in re.findall(r"\brv\d+\w*\b", low):          # rv32, rv32i, rv64gc …
        if m not in rv:
            rv.append(m)
    width = re.search(r"\b(\d+)\s*-?\s*bit\b", low)
    width_tok = [f"{width.group(1)}bit"] if width else []
    distinctive, generic = [], []
    for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_]+", low):
        if w in _SEARCH_STOP or len(w) < 3 or w in rv:
            continue
        (generic if w in _GENERIC_HDL else distinctive).append(w)
    out: List[str] = []
    for grp in (distinctive, rv, generic, width_tok):   # name → arch → role → width
        for w in grp:
            if w and w not in out:
                out.append(w)
    return out[:n]


_DESIGN_SYNS = [
    ("cpu", "processor", "core", "microprocessor"), ("rv32i", "riscv", "risc-v", "rv32"),
    ("pipelined", "pipeline"), ("accelerator", "engine", "coprocessor"),
    ("multiplier", "mac"), ("soc", "system-on-chip"), ("uart", "serial"),
]


def _design_variants(query: str, n: int = 3) -> List[str]:
    """A few CLOSE phrasings of the WHOLE prompt (synonyms of the same chip),
    used as EXTRA search queries when the exact wording returns little."""
    base = (query or "").strip().lower()
    if not base:
        return []
    out: List[str] = []
    for group in _DESIGN_SYNS:
        present = next((w for w in group if re.search(rf"\b{re.escape(w)}\b", base)), None)
        if not present:
            continue
        for alt in group:
            if alt == present:
                continue
            v = re.sub(rf"\b{re.escape(present)}\b", alt, base, count=1)
            if v != base and v not in out:
                out.append(v)
                break
        if len(out) >= n:
            break
    return out[:n]


# --------------------------------------------------------------------------- #
# Search backends: SearXNG (primary) → DuckDuckGo → GitHub API → googlesearch
# --------------------------------------------------------------------------- #
def searxng_url() -> str:
    return os.getenv("SEARXNG_URL", "http://localhost:8888").rstrip("/")


def searxng_available() -> bool:
    """True if a SearXNG instance answers on SEARXNG_URL (JSON format enabled)."""
    try:
        import requests
        r = requests.get(f"{searxng_url()}/search",
                         params={"q": "test", "format": "json"}, timeout=4)
        return r.ok and isinstance(r.json().get("results"), list)
    except Exception:  # noqa: BLE001
        return False


def _searxng_search(query: str, limit: int, categories: str = "",
                    engines: str = "") -> List[str]:
    """Primary search backend: a self-hosted SearXNG metasearch engine (aggregates
    Google/Bing/DuckDuckGo/GitHub/arXiv… in one query, no per-engine rate limits).
    Returns result URLs in relevance order. Falls back / tops up with DuckDuckGo."""
    out: List[str] = []
    base = os.getenv("SEARXNG_URL")
    probe_ok = True
    if not base and not os.getenv("SEARXNG_FORCE"):
        if not getattr(_searxng_search, "_probed", False):
            _searxng_search._probed = searxng_available()  # one cheap probe per process
        probe_ok = _searxng_search._probed
    if probe_ok:
        try:
            import requests
            params = {"q": query, "format": "json", "safesearch": 0}
            if categories:
                params["categories"] = categories
            if engines:
                params["engines"] = engines
            r = requests.get(f"{searxng_url()}/search", params=params, timeout=12)
            if r.ok:
                for res in r.json().get("results", []):
                    u = res.get("url")
                    if u and u not in out:
                        out.append(u)
                        if len(out) >= limit:
                            break
        except Exception:  # noqa: BLE001
            pass
    # FREE browser-quality top-up: the DuckDuckGo library answers without an API
    # key, so merge its results for GENERAL (non-`science`) searches. Papers stay
    # SearXNG-only (categories='science').
    if len(out) < limit and "science" not in categories:
        try:
            from ddgs import DDGS
            for res in DDGS().text(query, max_results=limit * 2):
                u = res.get("href")
                if u and u not in out:
                    out.append(u)
                    if len(out) >= limit:
                        break
        except Exception:  # noqa: BLE001
            pass
    return out[:limit]


# Sources that are NOT synthesizable plain Verilog for this GDSII flow —
# TL-Verilog / Makerchip / the RISC-V MYTH workshop.
_NONSYNTH_RE = re.compile(
    r"tl-verilog|tl-x\.org|makerchip|myth[_\s\-]?workshop|redwoodeda|transaction[-\s]?level",
    re.I)


def _ddg_github(query: str, limit: int) -> List[str]:
    """Repo finder via SearXNG (`site:github.com`), falling back to DuckDuckGo —
    works when the GitHub API is rate-limited or the prose query matched nothing."""
    out: List[str] = []
    kw = " ".join(_hdl_keywords(query, 3)) or query

    def _keep(u: str) -> None:
        m = re.match(r"(https://github\.com/[^/]+/[^/#?]+)", u or "")
        if (m and m.group(1) not in out and "/topics/" not in m.group(1)
                and not _NONSYNTH_RE.search(m.group(1))):
            out.append(m.group(1))

    for u in _searxng_search(f"{kw} verilog site:github.com", limit * 3):
        _keep(u)
        if len(out) >= limit:
            return out[:limit]
    try:
        from ddgs import DDGS
        for res in DDGS().text(f"{kw} verilog site:github.com", max_results=limit * 3):
            _keep(res.get("href", ""))
            if len(out) >= limit:
                break
    except Exception:  # noqa: BLE001
        pass
    return out[:limit]


def _github_hdl_repos(query: str, limit: int) -> List[str]:
    """Find real HDL repos with SHORT keyword queries (repo search hates prose), an
    optional token to dodge rate limits, and a DuckDuckGo `site:github.com` fallback."""
    out: List[str] = []
    headers = {"Accept": "application/vnd.github+json"}
    tok = os.getenv("GITHUB_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    kws = _hdl_keywords(query, 4)
    candidates = [q for q in dict.fromkeys(
        [" ".join(kws[:3]), " ".join(kws[:2]), kws[0] if kws else query.strip()]) if q]
    try:
        import requests
        for q in candidates:
            if len(out) >= limit:
                break
            r = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": f"{q} verilog", "sort": "stars", "per_page": 20},
                headers=headers, timeout=12)
            if not r.ok:
                break          # rate-limited/error → stop hitting the API, use the fallback
            for it in r.json().get("items", []):
                if it.get("language") in HDL_SET:
                    u = it.get("html_url")
                    if u and u not in out:
                        out.append(u)
                        if len(out) >= limit:
                            break
    except Exception:  # noqa: BLE001
        pass
    if len(out) < max(2, limit // 2):     # API thin or rate-limited → DDG site:github.com
        for u in _ddg_github(query, limit):
            if u not in out:
                out.append(u)
    return out[:limit]


def _web_search(query: str, similar: List[str] | None = None,
                n_github: int = 10, n_other: int = 10,
                suffix: str = "verilog digital design architecture") -> List[str]:
    """Balanced references: up to ``n_github`` HDL GitHub repos PLUS up to
    ``n_other`` papers/web pages (theory/knowledge). ``similar`` are extra,
    LLM-suggested building-block queries used when the exact IP isn't on GitHub."""
    gh: List[str] = []
    for q in [query] + (similar or []):
        if len(gh) >= n_github:
            break
        for u in _github_hdl_repos(q, n_github):
            if u not in gh:
                gh.append(u)

    other: List[str] = []
    full_q = f"{query} {suffix}".strip()
    for u in (_searxng_search(full_q, n_other * 2)
              + _searxng_search(f"{query} paper", max(2, n_other // 2), categories="science")):
        if u and "github.com" not in u and u not in other:
            other.append(u)
    # FALLBACK: DuckDuckGo — ONE pass per query fills BOTH lists: GitHub URLs
    # become anchor candidates, the rest become papers/web pages.
    if len(other) < n_other or len(gh) < 2:
        try:
            from ddgs import DDGS
            for q in [full_q] + [f"{s} {suffix}".strip() for s in (similar or [])[:2]]:
                for res in DDGS().text(q, max_results=(n_other + n_github) * 2):
                    u = res.get("href") or ""
                    if "github.com" in u:
                        m = re.match(r"(https://github\.com/[^/]+/[^/#?]+)", u)
                        if m and "/topics/" not in m.group(1) and m.group(1) not in gh:
                            gh.append(m.group(1))
                    elif u and u not in other:
                        other.append(u)
                if len(other) >= n_other and len(gh) >= 2:
                    break
        except Exception:  # noqa: BLE001
            pass

    if not gh and not other:  # last-ditch fallback
        try:
            from googlesearch import search
            for u in search(f"{query} verilog github", num_results=n_github + n_other):
                (gh if "github.com" in u else other).append(u)
        except Exception:  # noqa: BLE001
            pass

    return gh[:n_github] + other[:n_other]


# --------------------------------------------------------------------------- #
# Crawling + junk filtering
# --------------------------------------------------------------------------- #
def _md_text(res) -> str:
    md = getattr(res, "markdown", None)
    if md is None:
        return ""
    if isinstance(md, str):
        return md
    return getattr(md, "raw_markdown", None) or getattr(md, "fit_markdown", None) or str(md)


_JUNK_RE = re.compile(
    r"privacy preferences|we use cookies|cookie (policy|settings|consent)|consent (choices|"
    r"settings|management)|you are under 16|manage (your )?cookies|accept all cookies|"
    r"sign ?in to (continue|view|read)|create (a free )?account to|subscribe to (read|continue|"
    r"unlock)|log ?in to continue|are you a robot|verify you are human|captcha|enable javascript|"
    r"access denied|403 forbidden|404 not found|page not found|this site requires|"
    r"landing page|start (your )?free trial|get started (free|today|for free)|sign up (free|"
    r"now|today)|no credit card|pricing|add to cart|buy now|drag[- ]?drop|website builder|"
    r"tanpa (biaya|coding|hosting)|daftar (sekarang|gratis)|jualan|dashboard & builder|"
    r"pre[- ]?order|shop now|our products|built by engineers, for engineers", re.I)

_TECH_RE = re.compile(
    r"\b(module|endmodule|always|assign|wire|reg|posedge|parameter|localparam|register file|"
    r"pipeline|alu|opcode|instruction|fixed[- ]?point|datapath|fpga|asic|rtl|verilog|systemverilog|"
    r"vhdl|testbench|synthesis|riscv|risc-v|multiplier|adder|fsm|finite state)\b", re.I)

_WEB_CHROME_RE = re.compile(
    r"^\s*(skip to content|navigation menu|toggle navigation|sign in|sign up|appearance "
    r"settings|github copilot|mcp registry|developer workflows|application security|by "
    r"company size|by use case|view all features|why github|enterprises|startups|nonprofits|"
    r"\[devsecops\]|codespaces|changelog|marketplace)\b", re.I)


def _strip_web_chrome(md: str) -> str:
    """Drop obvious site-navigation boilerplate from crawled markdown so the
    digest is content, not menus."""
    if not md:
        return md
    return "\n".join(ln for ln in md.splitlines() if not _WEB_CHROME_RE.search(ln))


def _is_useful_doc(text: str, source: str = "") -> bool:
    """Reject crawled JUNK before it pollutes the knowledge: cookie-consent /
    privacy / login-wall / captcha pages, and nav-menu-dominated pages with no
    technical content. Keeps pages with real HDL/hardware signal."""
    t = (text or "").strip()
    if len(t) < 300:
        return False
    junk = len(_JUNK_RE.findall(t))
    tech = len(_TECH_RE.findall(t))
    lines = [ln for ln in t.splitlines() if ln.strip()]
    linky = sum(1 for ln in lines
                if "](" in ln and len(re.sub(r"\[[^\]]*\]\([^)]*\)", "", ln).strip()) < 15)
    link_density = linky / max(1, len(lines))
    if junk >= 2 and tech < 5:            # cookie/login wall with no substance
        return False
    if link_density > 0.55 and tech < 6:  # mostly a menu/link list
        return False
    if tech == 0 and len(t) < 1200:       # short and no hardware signal at all
        return False
    return True


def _looks_like_code(text: str) -> bool:
    """True when a snippet is dominated by HDL/source code rather than prose."""
    t = text[:1500]
    code = len(re.findall(
        r"[;{}]|`\w+|\\\w+|\b(module|endmodule|assign|always|wire|reg|input|output|logic|begin|end|"
        r"parameter|localparam)\b", t))
    words = len(re.findall(r"[A-Za-z]{3,}", t))
    return code > 25 or (words > 0 and code / words > 0.30)


def _clean_gist(text: str) -> str:
    """A clean prose gist from crawled markdown: drop site chrome, keep
    sentence-like lines, cap ~600 chars. '' if what's left is code or navigation."""
    body = _strip_web_chrome(text or "")
    keep = []
    for ln in body.splitlines():
        s = ln.strip()
        if len(s) < 25 or "](" in s or s.startswith(("#", "|", "-", "*", "`")):
            continue
        keep.append(s)
        if sum(len(k) for k in keep) > 700:
            break
    gist = re.sub(r"\s+", " ", " ".join(keep)).strip()
    return "" if (not gist or _looks_like_code(gist)) else gist[:600]


_TAG_RE = re.compile(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", re.S | re.I)
_HTML_RE = re.compile(r"<[^>]+>")


def _requests_page_text(url: str, timeout: float = 20) -> str:
    """Plain-requests HTML→text fallback used when crawl4ai isn't installed
    (it pulls Playwright + a Chromium download, too heavy for the service image)."""
    try:
        import requests
        r = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ChipOrchestra/1.0"})
        if not r.ok or "html" not in (r.headers.get("content-type") or "html"):
            return ""
        body = _TAG_RE.sub(" ", r.text)
        body = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", body, flags=re.I)
        text = _HTML_RE.sub(" ", body)
        text = re.sub(r"&nbsp;?", " ", text)
        text = re.sub(r"&amp;?", "&", text)
        text = "\n".join(re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines())
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    except Exception:  # noqa: BLE001
        return ""


def _crawl_urls(urls: List[str], limit: int = 8,
                deadline: "float | None" = None) -> List[Document]:
    """Crawl a handful of URLs into Documents. GitHub repos are NEVER crawled as
    HTML (just nav-menu chrome) — the REAL HDL source is fetched via the API
    instead. Web pages go through crawl4ai when available, else plain requests.
    `deadline` (absolute time.time()) hard-caps the whole call."""
    urls = urls[:limit]
    out: List[Document] = []

    gh = [u for u in urls if "github.com" in u]
    web = [u for u in urls if "github.com" not in u]
    for u in gh:
        if deadline and time.time() > deadline:
            break
        code = _github_code_text(u)
        if code and len(code) > 200:
            out.append(Document(page_content=code[:8000], metadata={"source": u}))

    crawl4ai_ok = True
    try:
        import asyncio
        from crawl4ai import AsyncWebCrawler
    except Exception:  # noqa: BLE001
        crawl4ai_ok = False

    if web and crawl4ai_ok:
        async def _crawl() -> None:
            sem = asyncio.Semaphore(5)
            async with AsyncWebCrawler() as crawler:
                async def fetch(url: str) -> None:
                    async with sem:
                        try:
                            res = await asyncio.wait_for(crawler.arun(url=url), timeout=25)
                        except Exception:  # noqa: BLE001
                            return
                    md = _strip_web_chrome(_md_text(res))
                    if md and _is_useful_doc(md, url):
                        out.append(Document(page_content=md[:8000], metadata={"source": url}))
                await asyncio.gather(*(fetch(u) for u in web))

        try:
            budget = float(os.getenv("GARUDA_CRAWL_BUDGET_S", str(min(150, 40 + 9 * len(web)))))
            if deadline:
                budget = max(5.0, min(budget, deadline - time.time()))
            asyncio.run(asyncio.wait_for(_crawl(), timeout=budget))
        except Exception as e:  # noqa: BLE001
            logger.warning("crawl failed (%s) — using %d page(s) gathered so far", e, len(out))
    elif web:
        for u in web:
            if deadline and time.time() > deadline:
                break
            md = _strip_web_chrome(_requests_page_text(u))
            if md and _is_useful_doc(md, u):
                out.append(Document(page_content=md[:8000], metadata={"source": u}))
    return out


# --------------------------------------------------------------------------- #
# GitHub source fetching
# --------------------------------------------------------------------------- #
def _gh_headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    tok = os.getenv("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _gh_hdl_paths(user: str, repo: str, headers: dict, max_files: int):
    """List up to max_files HDL blob paths in a GitHub repo + the default branch."""
    import requests
    info = requests.get(f"https://api.github.com/repos/{user}/{repo}", headers=headers, timeout=12)
    if not info.ok:
        return "main", []
    branch = info.json().get("default_branch", "main")
    tree = requests.get(
        f"https://api.github.com/repos/{user}/{repo}/git/trees/{branch}?recursive=1",
        headers=headers, timeout=15)
    if not tree.ok:
        return branch, []
    paths = [t["path"] for t in tree.json().get("tree", [])
             if t.get("type") == "blob"
             and t["path"].lower().endswith((".v", ".sv", ".vh", ".svh", ".vhd"))]
    paths.sort(key=lambda p: ("tb" in p.lower() or "test" in p.lower(), len(p)))
    return branch, paths[:max_files]


def _github_code_text(repo_url: str, max_files: int = 6, max_chars: int = 8000) -> str:
    """Fetch REAL HDL source (.v/.sv/.vh/.vhd) from a GitHub repo via the API and
    return it concatenated — NOT the repo's HTML landing page (nav-menu chrome)."""
    import requests
    m = re.search(r"github\.com/([^/]+)/([^/#?]+)", repo_url)
    if not m:
        return ""
    user, repo = m.group(1), m.group(2).replace(".git", "")
    try:
        h = _gh_headers()
        branch, paths = _gh_hdl_paths(user, repo, h, max_files)
        chunks, total = [], 0
        for path in paths:
            raw = requests.get(
                f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}", timeout=15)
            if raw.ok and raw.text.strip():
                snip = raw.text[:3000]
                chunks.append(f"// ===== {repo}/{path} =====\n{snip}")
                total += len(snip)
                if total >= max_chars:
                    break
        return "\n\n".join(chunks)[:max_chars]
    except Exception:  # noqa: BLE001
        return ""


def _repo_score(repo_url: str, query: str) -> int:
    """How well a repo NAME matches the request — the DISTINCTIVE keyword (the
    project name) counts most, so meiniKi/FazyRV beats a generic ultraembedded/
    riscv for the prompt 'fazyrv rv32i 8 bit'."""
    name = repo_url.lower().rsplit("/", 1)[-1]
    kws = _hdl_keywords(query, 6)
    score = 0
    for i, kw in enumerate(kws):
        if kw and kw in name:
            score += 5 if i == 0 else 1
    if kws and name == kws[0]:
        score += 5
    return score


def _clone_anchor_repo(repo_url: str, design_dir, max_files: int = 24) -> int:
    """Download MANY HDL files from ONE repo into context/anchor/<repo>/ — the
    reference the generator STUDIES (it learns the approach, then writes its own
    RTL; it does not copy these). PRIMARY path is `git clone --depth 1` (no
    GitHub API rate limit); the HTTP API is the fallback. Returns file count."""
    m = re.search(r"github\.com/([^/]+)/([^/#?]+)", repo_url)
    if not m:
        return 0
    user, repo = m.group(1), m.group(2).replace(".git", "")
    adir = Path(design_dir) / "context" / "anchor" / repo
    adir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []

    if shutil.which("git"):
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            proc = subprocess.run(
                ["git", "clone", "--depth", "1", "--quiet",
                 f"https://github.com/{user}/{repo}.git", tmp],
                capture_output=True, text=True, errors="replace",
                timeout=float(os.getenv("GARUDA_CLONE_TIMEOUT_S", "90")))
            if proc.returncode == 0:
                hdl = [p for p in Path(tmp).rglob("*")
                       if p.is_file() and p.suffix.lower() in (".v", ".sv", ".vh", ".svh")
                       and not re.search(r"(_tb|tb_|test|bench)", p.name, re.I)]
                hdl.sort(key=lambda p: (0 if "rtl" in [x.lower() for x in p.parts] else 1,
                                        len(str(p))))
                for p in hdl[:max_files]:
                    rel = p.relative_to(tmp)
                    fp = adir / re.sub(r"[^\w.\-]", "_", str(rel))
                    try:
                        fp.write_text(p.read_text(errors="replace"))
                        saved.append(fp)
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            pass
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if not saved:
        try:
            import requests
            h = _gh_headers()
            branch, paths = _gh_hdl_paths(user, repo, h, max_files)
            for path in paths:
                raw = requests.get(
                    f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}", timeout=15)
                if raw.ok and raw.text.strip():
                    fp = adir / re.sub(r"[^\w.\-]", "_", path)
                    fp.write_text(raw.text)
                    saved.append(fp)
        except Exception:  # noqa: BLE001
            pass
    return len(saved)


# --------------------------------------------------------------------------- #
# Error-query distillation + search-mode classification
# --------------------------------------------------------------------------- #
def _error_query(err: str) -> str:
    """Turn a compiler/lint error log into a concise web-search query (strip the
    file paths/line numbers and prefer the MOST DESCRIPTIVE error message)."""
    cands = []
    for line in (err or "").splitlines():
        low = line.lower()
        if "error" in low or "syntax" in low:
            msg = re.sub(r"^.*?:\s*\d+:?\s*", "", line)
            msg = re.sub(r"/[\w./\-]+\.s?vh?", "", msg).strip()
            if len(msg) > 8 and msg.lower().strip(". ") not in ("syntax error", "error", "%error"):
                cands.append(msg)
    if cands:
        return ("verilog " + max(cands, key=len))[:140]
    first = next((l.strip()
                 for l in (err or "").splitlines() if l.strip()), "")
    return ("verilog " + re.sub(r"^.*?:\s*\d+:?\s*", "", first))[:140]


# A query that IS an error/compiler message (fix-mode) vs a design/topic (learn-mode).
_ERRORISH_RE = re.compile(
    r"\berror\b|\bsyntax\b|\bfailed\b|\bwarning\b|unable to|cannot\b|mismatch|violation|"
    r"%\w+:|\.s?vh?:\d+|timed? ?out|undeclared|not a valid|multidriven|latch\b|"
    r"->\s*FAIL|expected\s*=", re.I)

# Within fix-mode: a DISTINCTIVE tool message (worth searching the web for) vs a
# DESIGN-SPECIFIC failure (watchdog timeout, handshake that never asserts) — the
# web cannot debug THIS design's FSM.
_TOOL_MSG_RE = re.compile(
    r"%(Error|Warning)|syntax error|Unable to (open|bind)|\.s?vh?:\d+|undeclared|"
    r"not a valid|unmapped|multidriven|combinational loop|\$readmem\w*:|give ?up", re.I)
_DESIGN_FAIL_RE = re.compile(
    r"time ?-?\s?out|hang|never (assert|deassert|finish|complet|unblock)|stuck|watchdog|"
    r"expected\s*=|->\s*FAIL|\bFAILED\b", re.I)


def _refine_search_query(query: str) -> str:
    """Distil a raw, possibly non-English/vague prompt into a CONCISE TECHNICAL
    ENGLISH hardware search phrase (≤10 words). Without this, a prompt like
    'buat object detection accelerator…' hits landing-page junk instead of
    RTL/architecture pages."""
    q = (query or "").strip()
    if not q:
        return q
    if len(q) <= 60 and q.isascii() and not re.search(r"\b(buat|gunakan|untuk|saya|ingin|dan)\b", q, re.I):
        return q
    try:
        out = get_chat_model(temperature=0.0).invoke(
            "Turn this hardware design request into a SHORT English web-search query for finding "
            "the DIGITAL-DESIGN / RTL architecture and papers behind it. Output ONLY the query: "
            "≤10 words, English technical keywords (module names, algorithm, 'verilog', "
            "'accelerator', 'architecture'), NO Indonesian, NO 'make/build', NO full sentences.\n"
            f"REQUEST: {q[:400]}")
        refined = re.sub(r"[\"'`\n]", " ", getattr(out, "content", "") or "").strip()[:120]
        return refined or q
    except Exception:  # noqa: BLE001
        return q


def _web_knowledge(query: str) -> str:
    """LEARN-mode web lookup — what a thing IS and how it's built in RTL. Used
    when a deep agent searches a TOPIC ('FazyRV RV32I CPU', '2x2 CGRA PE array')."""
    refined = _refine_search_query(query)
    logger.info("web lookup (learn): %s → %s", query[:80], refined[:80])
    try:
        urls = _web_search(refined, n_github=3, n_other=5)
        docs = _crawl_urls(urls, limit=5)
        if not docs:
            return ""
        body = "\n\n".join(f"[{d.metadata.get('source', '')}]\n{d.page_content[:1500]}"
                           for d in docs[:4])
        out = get_chat_model(temperature=0.2).invoke(
            "Digest these web results for a hardware engineer. Explain WHAT the topic is and "
            "HOW it is typically implemented in RTL: architecture, key modules and interfaces, "
            "important parameters, and pitfalls. Concrete and concise (≤25 lines). Do NOT "
            f"invent an error to fix — this is a knowledge lookup.\nTOPIC: {query}\n\n"
            f"WEB RESULTS:\n{body}")
        summary = clean_llm_output(getattr(out, "content", "") or "")
        return f"WEB KNOWLEDGE for '{query}':\n{summary[:3000]}"
    except Exception as e:  # noqa: BLE001
        logger.warning("web lookup failed (%s)", e)
        return ""


def _auto_research(query: str) -> str:
    """Autonomously search the WEB for how to fix an error and summarize the fix —
    the corrector calls this on its own when it's stuck (no human needed)."""
    logger.info("web fix search: %s", query[:100])
    try:
        # n_github=0: fix-mode gets forum/doc/issue pages — a bare REPO HOMEPAGE
        # carries no fix and wastes the crawl. suffix 'fix': the default suffix
        # skews an ERROR query toward architecture pages instead of solutions.
        urls = _web_search(query, n_github=0, n_other=6, suffix="fix")
        docs = _crawl_urls(urls, limit=4)
        if not docs:
            return ""
        body = "\n\n".join(d.page_content[:1500] for d in docs[:3])
        out = get_chat_model(temperature=0.2).invoke(
            "From these web results, explain CONCISELY how to fix this Verilog error and show the "
            f"CORRECT code pattern (a few lines).\n\nERROR: {query}\n\nWEB RESULTS:\n{body}")
        summary = clean_llm_output(getattr(out, "content", "") or "")
        return f"WEB FIX HINT for '{query}':\n{summary}"
    except Exception as e:  # noqa: BLE001
        logger.warning("web research failed (%s)", e)
        return ""


def web_research_enabled() -> bool:
    """Web research is on unless explicitly disabled (AGENT_WEB_RESEARCH=0)."""
    return os.getenv("AGENT_WEB_RESEARCH", "1").strip().lower() not in ("0", "false", "no", "off")


# --------------------------------------------------------------------------- #
# Step tools: search_web / recall_memory / fetch_reference (GarudaChip parity)
# --------------------------------------------------------------------------- #
def make_step_tools(base_dir=None) -> List:
    """Step-specific tools every deep-agent node gets, on top of the file tools:
    autonomous WEB research, persistent MEMORY recall, and on-demand reference
    fetching. `base_dir` sandboxes the reference paths to the task workspace."""
    base = Path(base_dir).resolve() if base_dir else None

    def _resolve(path: str) -> Path:
        p = (base / (path or "")).resolve() if base else Path(path or "").resolve()
        if base and p != base and base not in p.parents:
            raise ValueError(f"path '{path}' escapes the design directory")
        return p

    @tool
    def search_web(query: str) -> str:
        """Search the web. TWO modes, picked automatically from the query:
        • an ERROR / compiler message → a fix hint with the correct code pattern;
        • a design/topic (e.g. 'FazyRV RV32I CPU', 'CGRA PE array') → a KNOWLEDGE digest:
          what it is and how it's implemented in RTL (architecture, modules, pitfalls).
        NOT searchable: a design-specific hang/timeout/value mismatch (the web can't debug
        THIS design) — those return guidance to the tools that can."""
        if not web_research_enabled():
            return "(web research is disabled: set AGENT_WEB_RESEARCH=1 to enable)"
        if _ERRORISH_RE.search(query or ""):
            if _DESIGN_FAIL_RE.search(query or "") and not _TOOL_MSG_RE.search(query or ""):
                return ("(web search skipped: this failure is DESIGN-SPECIFIC — nobody on the "
                        "web has your FSM, so a search returns generic homepages. Debug from "
                        "the design's own evidence instead: 1) re-read the failure output — "
                        "which wait/handshake never unblocked, which case mismatched; "
                        "2) run_python a golden model to COMPUTE the expected values; "
                        "3) recall_memory for a stored lesson; 4) read context/ for what "
                        "earlier attempts already tried.)")
            q = _error_query(query) if ("\n" in (query or "")
                                        or re.search(r"\.s?vh?:\d+", query or "")) else query
            return _auto_research(q) or "(no useful web results)"
        return _web_knowledge(query) or "(no useful web results)"

    @tool
    def recall_memory(topic: str) -> str:
        """Recall a remembered fix/lesson for an error message or topic from past runs."""
        from lessons import recall_fix
        return recall_fix(_error_query(topic)) or recall_fix(topic) or "(nothing remembered yet)"

    @tool
    def fetch_reference(url: str) -> str:
        """Retrieve ONE more reference ON DEMAND from a link in context/sources.md — use
        this only if the references in context/anchor/ are NOT a good fit for the spec.
        For a GitHub repo it fetches the real HDL; for a paper/web page it crawls the text.
        The result is also saved under context/refs/ so you can read_file_disk it. Pass the
        exact URL from context/sources.md."""
        url = (url or "").strip()
        if not url.startswith("http"):
            return "(pass a full URL from context/sources.md)"
        if base is None:
            return "(no workspace available)"
        try:
            if "github.com" in url:
                code = _github_code_text(url, max_files=8, max_chars=9000)
                if code:
                    p = base / "context" / "refs" / (re.sub(r"[^\w]", "_", url)[-60:] + ".v")
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(code)
                    return f"Saved HDL to {p.relative_to(base)}.\n\n{code[:3500]}"
            docs = _crawl_urls([url], limit=1)
            if docs:
                body = docs[0].page_content[:3500]
                p = base / "context" / "refs" / (re.sub(r"[^\w]", "_", url)[-60:] + ".md")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(docs[0].page_content[:9000])
                return f"Saved to {p.relative_to(base)}.\n\n{body}"
        except Exception as e:  # noqa: BLE001
            return f"(could not fetch {url}: {e})"
        return f"(nothing usable at {url})"

    tools = [recall_memory]
    if web_research_enabled():
        tools = [search_web, recall_memory, fetch_reference]
    return tools


# --------------------------------------------------------------------------- #
# PLAN-stage reference gathering (understand → sources.md → anchor clone)
# --------------------------------------------------------------------------- #
def gather_references(query: str, design_dir, max_repos: int = 6, max_other: int = 6,
                      budget_s: float = 0.0) -> Dict[str, object]:
    """The compact 'anchor + links' reference hunt run once per task (PLAN stage):
      1. UNDERSTAND the prompt — search it, crawl the top hits, keep a short gist
         → context/understanding.md;
      2. Collect balanced references (GitHub HDL repos + papers/pages)
         → context/sources.md;
      3. CLONE the best-matching repo's HDL into context/anchor/ for the
         generator to study (learn the approach, write its own RTL).
    Returns {'understanding': str, 'sources': [urls], 'anchor_files': int}."""
    design_dir = Path(design_dir)
    ctx_dir = design_dir / "context"
    ctx_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + (budget_s or float(os.getenv("GARUDA_RESEARCH_BUDGET_S", "420")))

    refined = _refine_search_query(query)
    urls = _web_search(refined, similar=_design_variants(refined),
                       n_github=max_repos, n_other=max_other)
    gh = [u for u in urls if "github.com" in u]
    other = [u for u in urls if "github.com" not in u]

    # 1) understanding gist from the top non-GitHub pages
    understanding = ""
    docs = _crawl_urls(other[:3], limit=3, deadline=deadline)
    gists = [g for g in (_clean_gist(d.page_content) for d in docs) if g]
    if gists:
        understanding = "\n\n".join(f"- {g}" for g in gists[:3])
        (ctx_dir / "understanding.md").write_text(
            f"# What this design is (web understanding)\n\nQuery: {refined}\n\n{understanding}\n")

    # 2) sources.md — every reference link, best repo first
    gh.sort(key=lambda u: -_repo_score(u, refined))
    lines = ["# Reference sources (gathered from the web)", "", "## HDL repositories"]
    lines += [f"- {u}" for u in gh] or ["- (none found)"]
    lines += ["", "## Papers / articles"]
    lines += [f"- {u}" for u in other] or ["- (none found)"]
    (ctx_dir / "sources.md").write_text("\n".join(lines) + "\n")

    # 3) anchor: clone the best-scoring repo's HDL for the generator to study
    anchor_files = 0
    for u in gh[:2]:
        if time.time() > deadline:
            break
        anchor_files = _clone_anchor_repo(u, design_dir)
        if anchor_files:
            break
    return {"understanding": understanding, "sources": gh + other,
            "anchor_files": anchor_files}


__all__ = [
    "clean_llm_output",
    "searxng_url",
    "searxng_available",
    "web_research_enabled",
    "make_step_tools",
    "gather_references",
]
