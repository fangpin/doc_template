VENV := .venv
PY := $(VENV)/bin/python
SPHINX := $(VENV)/bin/sphinx-build

.PHONY: install sync html docs serve clean

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

ifndef FROM
sync:
	$(PY) doc_scripts/sync_lark_doc.py $(if $(DOC),--doc "$(DOC)")
else
sync:
	$(PY) doc_scripts/sync_lark_doc.py --from-file "$(FROM)"
endif

html:
	$(SPHINX) -b html docs/source docs/_build/html

docs: sync html
	@echo "open docs/_build/html/index.html"

serve: html
	$(PY) -m http.server 8000 --directory docs/_build/html

clean:
	rm -rf docs/_build
