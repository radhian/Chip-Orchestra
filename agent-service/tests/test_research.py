from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import _gh_hdl_paths


def test_github_hdl_paths_prefers_main_branch() -> None:
    info = Mock(ok=True)
    info.json.return_value = {"default_branch": "master"}
    main_tree = Mock(ok=True)
    main_tree.json.return_value = {
        "tree": [{"type": "blob", "path": "rtl/top.sv"}],
    }

    with patch("requests.get", side_effect=[info, main_tree]) as get:
        branch, paths = _gh_hdl_paths("owner", "repo", {}, 6)

    assert branch == "main"
    assert paths == ["rtl/top.sv"]
    assert get.call_args_list[1].args[0].endswith("/git/trees/main?recursive=1")


def test_github_hdl_paths_falls_back_to_default_branch() -> None:
    info = Mock(ok=True)
    info.json.return_value = {"default_branch": "master"}
    main_tree = Mock(ok=False)
    default_tree = Mock(ok=True)
    default_tree.json.return_value = {
        "tree": [{"type": "blob", "path": "rtl/top.v"}],
    }

    with patch("requests.get", side_effect=[info, main_tree, default_tree]) as get:
        branch, paths = _gh_hdl_paths("owner", "repo", {}, 6)

    assert branch == "master"
    assert paths == ["rtl/top.v"]
    assert get.call_args_list[1].args[0].endswith("/git/trees/main?recursive=1")
    assert get.call_args_list[2].args[0].endswith("/git/trees/master?recursive=1")
