#!/usr/bin/env bash
# Vendor this documentation template into another repository's root directory.
#
# From a local clone:
#   ./install.sh /path/to/target-repo
#
# Directly from GitHub (once this repo is public):
#   curl -sSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.sh | bash -s -- /path/to/target-repo
#
# Pin a ref (tag/commit) instead of main:
#   REF=v1.0.0 bash install.sh /path/to/target-repo
#
# Idempotent: template-owned files are overwritten, everything else is left alone.

set -euo pipefail

OWNER_REPO="${OWNER_REPO:-}"   # e.g. yourname/doc_template; required for curl mode
REF="${REF:-main}"
TARGET="${1:?usage: bash install.sh <target-repo-root>}"

# Files that belong to the template (paths relative to repo root). Sync-generated
# content (docs/source/chapters, assets, index.md, project.json) is intentionally
# NOT vendored -- each target repo generates its own via `make -f doc.mk docs`.
ITEMS=(doc.mk install.sh requirements-docs.txt doc_scripts docs/source/conf.py .github/workflows/docs.yml)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"

if [[ -n "${BASH_SOURCE[0]:-}" && -f "$SCRIPT_DIR/doc.mk" ]]; then
    SRC="$SCRIPT_DIR"
else
    # curl|bash mode: fetch the tarball of the requested ref
    [[ -n "$OWNER_REPO" ]] || { echo "error: set OWNER_REPO=<owner>/<repo> for remote install" >&2; exit 1; }
    SRC="$(mktemp -d)"
    trap 'rm -rf "$SRC"' EXIT
    curl -fsSL "https://codeload.github.com/$OWNER_REPO/tar.gz/refs/heads/$REF" \
        | tar -xz --strip-components=1 -C "$SRC"
fi

if [[ -f "$TARGET/doc.mk" ]]; then
    echo "note: doc.mk already exists in target; template files will be updated in place"
fi

for item in "${ITEMS[@]}"; do
    mkdir -p "$TARGET/$(dirname "$item")"
    cp -R "$SRC/$item" "$TARGET/$(dirname "$item")/"
    echo "  vendored: $item"
done

# Make sure generated artifacts don't get committed in the target repo.
for entry in ".venv/" "docs/_build/" "dist/platform-posts/"; do
    touch "$TARGET/.gitignore"
    grep -qxF "$entry" "$TARGET/.gitignore" || echo "$entry" >> "$TARGET/.gitignore"
done

cat <<EOF

Done. Next steps in the target repo:
  1. Install toolchain:      make -f doc.mk docs-install
  2. Build the doc site:     make -f doc.mk docs DOC="<feishu-doc-url>"
  3. Enable GitHub Pages:    Settings -> Pages -> Source -> GitHub Actions
  4. Commit the vendored files (docs/source included) and push.
EOF
