import json
from pathlib import Path

meta_path = Path(__file__).resolve().parent.parent / "project.json"
meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

project = meta.get("title", "Docs")
author = ""

extensions = ["myst_parser"]
myst_enable_extensions = [
    "amsmath",
    "colon_fence",
    "deflist",
    "dollarmath",
    "tasklist",
]
myst_heading_anchors = 3
source_suffix = {".md": "markdown"}
exclude_patterns = ["_build"]

html_theme = "sphinx_rtd_theme"
html_title = project
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 3,
}
