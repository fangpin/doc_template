# Standalone template repo: keep short target names (make docs / make install).
# When vendored into another project, use doc.mk directly (make -f doc.mk docs)
# or add `include doc.mk` to the host Makefile and call the docs-* targets.

include doc.mk

.PHONY: install sync html export docs serve clean

install: docs-install
sync: docs-sync
html: docs-html
export: docs-export
serve: docs-serve
clean: docs-clean
