# doc_template

Turn a Feishu (Lark) document into a Sphinx-powered documentation site
(Read the Docs theme + MyST Markdown) with a **single command**, deploy it to
GitHub Pages automatically, and additionally produce a set of markdown files
tailored for publishing on third-party platforms (Zhihu, Juejin, WeChat, ...).

This repository is a template:

- **Use it directly as a docs site**: clone it, run one command, deploy;
- **Vendor it into any existing project**: `install.sh` copies the toolchain
  flat into the target repo's root (no extra directory layer, no submodules).
  Each project just points at a different Feishu document URL.

## Features

- Fetches Feishu documents via `lark-cli` (Markdown format) and splits chapters on H1 headings
- Images are downloaded and localized; embedded Feishu sheets are expanded into Markdown tables
- Math (`$...$` / `$$...$$`) rendered with MathJax; code fence languages normalized to Pygments names
- A per-page table of contents at the top of every chapter (Spinning Up style)
- "Edit on GitHub" link in the page header (repo info auto-detected from git remote / CI env)
- Exports `dist/platform-posts/*.md` with image URLs rewritten to public absolute URLs
- GitHub Actions builds and deploys to Pages; CI needs no Feishu credentials
  (synced sources are committed with the repo)

## Prerequisites

- Python 3.10+
- `lark-cli` (only needed for local sync; `make install` installs `@larksuite/cli`
  via npm automatically — afterwards run `lark-cli auth login` once)

## Quick Start (using this repo directly)

```bash
make install                                        # first time: venv, deps, lark-cli check
make docs DOC="https://xxx.feishu.cn/docx/XXXX"     # fetch + split + localize + build
make serve                                          # preview at http://127.0.0.1:8000/
```

Re-syncing the same document does not need the URL again — `make docs` reuses
the address recorded in `docs/project.json`.

Other useful commands:

```bash
make sync DOC=<url>        # regenerate docs/source/ only
make html                  # build HTML only
make export                # export the publishing markdown only (see below)
make sync FROM=local.md    # offline: build from a local markdown file, no Feishu
```

## Deploy to GitHub Pages

1. Run `make docs DOC=<url>`, then **commit `docs/source/`** (chapters, images, tables).
2. Repo Settings -> Pages -> Source: choose **GitHub Actions**.
3. Push to `main` / `master`; `.github/workflows/docs.yml` builds and deploys.
4. Site URL: `https://<owner>.github.io/<repo>/`.

## Vendor into Another Project (flat install)

Run from the **target project's root**:

```bash
curl -sSL https://raw.githubusercontent.com/fangpin/doc_template/master/install.sh | bash
make -f doc.mk docs-install
make -f doc.mk docs DOC="<feishu-doc-url>"
```

Files copied into the target repo root: `doc.mk`, `doc_scripts/`,
`docs/source/conf.py`, `requirements-docs.txt`, `.github/workflows/docs.yml`,
`install.sh`. The target's own `Makefile` / `requirements.txt` are never
touched (that's why they are named differently). To integrate with a project's
own Makefile, add `include doc.mk` and use the `docs` / `docs-sync` targets.
Upgrading is the same curl command again (idempotent overwrite); pin a version
with the `REF` env var, e.g. `REF=v1.0.0`.

## Publishing to Other Platforms (Zhihu / Juejin / WeChat / ...)

`make docs` also produces `dist/platform-posts/`: one Markdown file per chapter
with Sphinx-only directives stripped and image URLs rewritten to public
absolute URLs. Two image URL modes:

```bash
make export                    # default "pages": links to the deployed site's _images/
                               # (best fetch success rate for CN platforms; requires Pages deployed)
make export IMAGE_BASE=raw     # "raw": links to raw.githubusercontent.com repo files
                               # (works as soon as you push; stable paths)
```

## Configuration

The generated `docs/project.json` (committed per instance repo) is the
configuration surface:

```json
{
  "title": "site title",
  "source": "Feishu doc URL (reused when make sync is run without DOC)",
  "github_repo": "owner/repo (overrides git-remote detection)",
  "github_branch": "main",
  "site_url": "https://owner.github.io/repo/ (overrides site URL detection)"
}
```

Sphinx-level settings (theme, extensions) live in
[docs/source/conf.py](docs/source/conf.py).

## How It Works

```
Feishu doc --(lark-cli)--> doc_scripts/sync_lark_doc.py
  |-- sanitize MyST-incompatible syntax (false footnotes, fence languages, escapes)
  |-- <sheet> embeds --(lark-cli sheets +csv-get)--> Markdown tables
  |-- split on H1 -> docs/source/chapters/NN-<slug>.md (page TOC inserted)
  |-- download images -> docs/source/assets/images/, rewrite references
  `-- write docs/source/index.md + docs/project.json
sphinx-build (myst-parser + sphinx_rtd_theme) -> docs/_build/html/
doc_scripts/export_platform_posts.py -> dist/platform-posts/*.md (public image URLs)
```

## Notes

- Chapters split on H1 headings. Slugs keep ASCII only; a purely Chinese title
  degrades to `NN-chapter` (affects URLs/filenames only, not displayed titles).
- Sync requires a logged-in `lark-cli` on your machine; CI only builds.
- Feishu image URLs are temporary signed URLs; sync localizes them, so commit
  `docs/source/` promptly.
- Embedded sheets export display values (first row = header); the read window
  is `A1:Z200`, larger sheets warn during sync.

## Repository Layout

```
Makefile                    # convenience entry for this repo (delegates to doc.mk)
doc.mk                      # all make targets (docs-install / docs-sync / docs-html / ...)
install.sh                  # flat-install into another repo (local or curl | bash)
requirements-docs.txt       # pinned Python dependencies
doc_scripts/
  sync_lark_doc.py          # Feishu -> Sphinx sources
  export_platform_posts.py  # -> platform publishing markdown
docs/
  source/conf.py            # Sphinx config (the only static source file in the template)
  _build/html/              # build output (git-ignored)
.github/workflows/docs.yml  # Pages build & deploy
```
