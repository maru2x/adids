ROOT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
VENV_PYTHON := $(ROOT_DIR)/.venv/bin/python

ifneq ($(wildcard $(VENV_PYTHON)),)
PYTHON ?= $(VENV_PYTHON)
else
PYTHON ?= python3
endif

.PHONY: venv
venv:
	@/usr/bin/python3.11 -m venv "$(ROOT_DIR)/.venv"

.PHONY: install
install:
	@"$(ROOT_DIR)/.venv/bin/python" -m pip install --upgrade pip
	@"$(ROOT_DIR)/.venv/bin/python" -m pip install -r "$(ROOT_DIR)/requirements.txt"

.PHONY: bootstrap
bootstrap: venv install

.PHONY: run
run:
	@cd "$(ROOT_DIR)/src/main" && "$(PYTHON)" Run.py

.PHONY: docs-check
docs-check:
	@"$(PYTHON)" -m unittest discover -s "$(ROOT_DIR)/tests" -p 'test_docs_consistency.py' -v -b

.PHONY: test
test:
	@"$(PYTHON)" -m compileall -q "$(ROOT_DIR)/src" "$(ROOT_DIR)/tests"
	@"$(PYTHON)" -m unittest discover -s "$(ROOT_DIR)/tests" -p 'test_*.py' -v -b

.PHONY: pcap-to-log
pcap-to-log:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/FeatureExtract/Zeek/PcapToLogExtractor.py"

.PHONY: log-to-csv
log-to-csv:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/FeatureExtract/Zeek/LogToCsvExtractor.py"
