#!/usr/bin/env python3
"""Fetch a Feishu (Lark) document via lark-cli and regenerate the Sphinx source tree.

Usage:
    python scripts/sync_lark_doc.py --doc <feishu-doc-url-or-token> [--title NAME]
    python scripts/sync_lark_doc.py --from-file <markdown-file>   # offline/testing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "docs" / "source"
CHAPTERS_DIR = SOURCE_DIR / "chapters"
IMAGES_DIR = SOURCE_DIR / "assets" / "images"
PROJECT_JSON = ROOT / "docs" / "project.json"

CONTENT_TYPE_EXT = {
    "image/apng": ".apng",
    "image/avif": ".avif",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}

TITLE_TAG_RE = re.compile(r"^<title>([\s\S]*?)</title>\s*")
H1_RE = re.compile(r"^#\s+\S")
H2_RE = re.compile(r"^#{2,6}\s+\S")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
ESCAPE_RE = re.compile(r"\\([*_$\[\]()])")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:")
FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]]+)\]")
SHEET_RE = re.compile(r"<sheet\b[^>]*>\s*(?:</sheet>)?")
FENCE_LANG_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*(\S*)(.*)$")

FENCE_LANG_ALIASES = {
    "plain": "text",
    "plaintext": "text",
    "txt": "text",
    "shell": "bash",
    "sh": "bash",
}

try:
    from pygments.lexers import get_lexer_by_name
except ImportError:  # sync runs without the docs venv; skip lexer validation
    get_lexer_by_name = None


def fail(message: str) -> None:
    sys.exit(f"error: {message}")


def fetch_lark_markdown(doc: str) -> str:
    if not shutil.which("lark-cli"):
        fail("lark-cli not found. Install it and run `lark-cli auth login` first.")
    env = {
        **os.environ,
        "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
        "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
    }
    proc = subprocess.run(
        ["lark-cli", "docs", "+fetch", "--doc", doc,
         "--doc-format", "markdown", "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        fail(f"lark-cli failed with status {proc.returncode}:\n{proc.stderr or proc.stdout}")
    out = proc.stdout
    try:
        payload = json.loads(out[out.index("{"): out.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        fail(f"unexpected lark-cli output:\n{out[:500]}")
    if not payload.get("ok"):
        fail(f"lark-cli returned an error:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
    return payload["data"]["document"]["content"]


def clean_title(title: str) -> str:
    title = re.sub(r"<[^>]+>", "", title)
    title = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", title)
    title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
    title = re.sub(r"[`*_~]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def slugify(title: str, index: int, seen: set[str]) -> str:
    cleaned = unicodedata.normalize("NFKD", clean_title(title)).lower()
    base = re.sub(r"[^a-z0-9]+", "-", cleaned).strip("-") or "chapter"
    slug = f"{index:02d}-{base}"
    suffix = 2
    while slug in seen:
        slug = f"{index:02d}-{base}-{suffix}"
        suffix += 1
    seen.add(slug)
    return slug


def normalize_fence_line(line: str) -> str:
    """Normalize fence info strings to something Pygments can highlight."""
    m = FENCE_LANG_RE.match(line)
    if not m:
        return line
    indent, fence, lang, _rest = m.groups()
    if not lang:
        return f"{indent}{fence}"
    token = FENCE_LANG_ALIASES.get(lang.lower(), lang.lower())
    if get_lexer_by_name is not None and token != "text":
        try:
            get_lexer_by_name(token)
        except Exception:
            print(f"  warning: unknown code language '{lang}', falling back to 'text'",
                  file=sys.stderr)
            token = "text"
    return f"{indent}{fence}{token}"


def cleanup_markdown(text: str) -> str:
    """Sanitize lark-cli markdown for MyST:

    - replace <sheet> embeds (content is not exported) with a visible placeholder
    - undo escape artifacts (\\*, \\$, \\(, ...) outside code fences
    - escape `[^...]` tokens that are regex character classes, not real footnotes
    - normalize code fence languages to Pygments-compatible names
    """
    text = SHEET_RE.sub("\n> [飞书内嵌电子表格未导出，请到原文档查看对应内容]\n", text)
    defined_footnotes = {
        m.group(1)
        for line in text.split("\n")
        if (m := FOOTNOTE_DEF_RE.match(line))
    }

    def escape_false_footnotes(line: str) -> str:
        return FOOTNOTE_REF_RE.sub(
            lambda m: m.group(0) if m.group(1) in defined_footnotes
            else "\\[" + m.group(0)[1:],
            line,
        )

    out, in_fence = [], False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(normalize_fence_line(line))
        elif in_fence:
            out.append(line)
        else:
            out.append(escape_false_footnotes(ESCAPE_RE.sub(r"\1", line)))
    return "\n".join(out)


def split_chapters(markdown: str) -> tuple[str | None, str, list[str]]:
    """Return (document title, preface, chapters). Chapters are split on H1 headings."""
    m = TITLE_TAG_RE.match(markdown)
    doc_title = clean_title(m.group(1)) if m else None
    body = markdown[m.end():] if m else markdown
    lines = body.split("\n")
    starts, in_fence = [], False
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence and H1_RE.match(line):
            starts.append(i)
    preface_end = starts[0] if starts else len(lines)
    preface = "\n".join(lines[:preface_end]).strip()
    chapters = [
        "\n".join(lines[start:(starts[pos + 1] if pos + 1 < len(starts) else len(lines))]).strip()
        for pos, start in enumerate(starts)
    ]
    return doc_title, preface, chapters


def extension_for(data: bytes, content_type: str | None) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:6].startswith(b"GIF"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    ct = (content_type or "").split(";")[0].strip().lower()
    return CONTENT_TYPE_EXT.get(ct, ".png")


def localize_images(content: str, slug: str) -> str:
    """Download remote images into docs/source/assets and rewrite references."""
    urls: list[str] = []
    for m in IMAGE_RE.finditer(content):
        url = m.group(2)
        if url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
    replacements: dict[str, str] = {}
    for i, url in enumerate(urls, 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                ext = extension_for(data, resp.headers.get("Content-Type"))
        except (urllib.error.URLError, OSError) as exc:
            print(f"  warning: failed to download image ({exc}): {url[:120]}", file=sys.stderr)
            continue
        dest = IMAGES_DIR / slug
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"image-{i:02d}{ext}").write_bytes(data)
        replacements[url] = f"../assets/images/{slug}/image-{i:02d}{ext}"

    def sub(m: re.Match) -> str:
        url = m.group(2)
        if url in replacements:
            return f"![{m.group(1)}]({replacements[url]}{m.group(3) or ''})"
        return m.group(0)

    return IMAGE_RE.sub(sub, content)


def add_page_toc(content: str) -> str:
    """Insert a local page TOC after the chapter H1 (Spinning Up style)."""
    lines = content.split("\n")
    body = lines[1:]
    in_fence = any_h2 = False
    for line in body:
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence and H2_RE.match(line):
            any_h2 = True
            break
    if not any_h2:
        return content
    toc = ["", "```{contents} 本页目录", "---", "depth: 2", "local: true", "---", "```"]
    return "\n".join([lines[0]] + toc + lines[1:])


def write_index(title: str, preface: str, slugs: list[str]) -> None:
    toctree = "\n".join(f"chapters/{slug}" for slug in slugs)
    parts = [f"# {title}\n"]
    if preface:
        parts.append(preface + "\n")
    parts.append(
        "```{toctree}\n"
        ":maxdepth: 2\n"
        ":caption: 目录\n"
        "\n"
        f"{toctree}\n"
        "```\n"
    )
    (SOURCE_DIR / "index.md").write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", default=os.environ.get("LARK_DOC_URL"),
                        help="Feishu document URL or token (or set LARK_DOC_URL)")
    parser.add_argument("--title", help="Override the site/chapter title")
    parser.add_argument("--from-file", help="Read markdown from a local file instead of lark-cli")
    args = parser.parse_args()

    if args.from_file:
        markdown = Path(args.from_file).read_text(encoding="utf-8")
    else:
        if not args.doc and PROJECT_JSON.exists():
            recorded = json.loads(PROJECT_JSON.read_text(encoding="utf-8")).get("source", "")
            if recorded != "local-file":
                args.doc = recorded
        if not args.doc:
            fail("missing document: pass --doc <url> or set LARK_DOC_URL")
        markdown = fetch_lark_markdown(args.doc)

    doc_title, preface, chapters = split_chapters(cleanup_markdown(markdown))
    title = args.title or doc_title or "Docs"
    if not chapters and not preface:
        fail("document is empty after parsing")

    # Regenerate only what we own; conf.py and user additions stay untouched.
    shutil.rmtree(CHAPTERS_DIR, ignore_errors=True)
    shutil.rmtree(IMAGES_DIR, ignore_errors=True)
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    slugs = []
    for index, content in enumerate(chapters, 1):
        heading = content.split("\n", 1)[0]
        slug = slugify(heading.lstrip("# ").strip(), index, seen)
        slugs.append(slug)
        content = add_page_toc(localize_images(content, slug))
        (CHAPTERS_DIR / f"{slug}.md").write_text(content + "\n", encoding="utf-8")
        print(f"  chapter: {slug}")

    write_index(title, preface, slugs)
    PROJECT_JSON.write_text(
        json.dumps(
            {
                "title": title,
                "source": "local-file" if args.from_file else args.doc,
                "synced_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"synced {len(slugs)} chapter(s) -> docs/source (title: {title})")


if __name__ == "__main__":
    main()
