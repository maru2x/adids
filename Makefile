ROOT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
VENV_PYTHON := $(ROOT_DIR)/.venv/bin/python
PYENV_BIN := $(HOME)/.pyenv/bin/pyenv
BOOTSTRAP_PYTHON := $(shell if [ -x "$(PYENV_BIN)" ] && [ -f "$(ROOT_DIR)/.python-version" ]; then "$(PYENV_BIN)" which python 2>/dev/null; elif command -v python3.11 >/dev/null 2>&1; then command -v python3.11; elif command -v python >/dev/null 2>&1; then command -v python; else command -v python3; fi)

ifneq ($(wildcard $(VENV_PYTHON)),)
PYTHON ?= $(VENV_PYTHON)
else
PYTHON ?= python3
endif

SCHEMA ?= zeek

.PHONY: venv
venv:
	@BOOTSTRAP_VERSION="$$("$(BOOTSTRAP_PYTHON)" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"; \
	if [ "$$BOOTSTRAP_VERSION" != "3.11" ]; then \
		echo "make bootstrap requires Python 3.11; found $$BOOTSTRAP_VERSION at $(BOOTSTRAP_PYTHON)" >&2; \
		exit 1; \
	fi
	@if [ -d "$(ROOT_DIR)/.venv/bin" ]; then chmod u+w "$(ROOT_DIR)"/.venv/bin/activate* "$(ROOT_DIR)"/.venv/bin/Activate* 2>/dev/null || true; fi
	@"$(BOOTSTRAP_PYTHON)" -m venv "$(ROOT_DIR)/.venv"

.PHONY: install
install:
	@"$(ROOT_DIR)/.venv/bin/python" -m pip install --upgrade pip
	@"$(ROOT_DIR)/.venv/bin/python" -m pip install -r "$(ROOT_DIR)/requirements.txt"

.PHONY: bootstrap
bootstrap: venv install

.PHONY: run
run:
	@cd "$(ROOT_DIR)/src/main" && "$(PYTHON)" run.py

.PHONY: unit-test
unit-test:
	@"$(PYTHON)" -m compileall -q "$(ROOT_DIR)/src"
	@"$(PYTHON)" -m pytest "$(ROOT_DIR)/tests/unit" -q

.PHONY: test-e2e
test-e2e:
	@"$(PYTHON)" -m pytest "$(ROOT_DIR)/tests/e2e" -q -m e2e

.PHONY: test-DataModif
test-DataModif:
	@"$(PYTHON)" -m pytest "$(ROOT_DIR)/tests/e2e/data_modified" -q -m e2e

.PHONY: test-all
test-all: unit-test test-e2e

.PHONY: pcap-to-log
pcap-to-log:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py"

.PHONY: log-to-csv
log-to-csv:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/FeatureExtract/Zeek/log_to_csv_extractor.py"

.PHONY: align-mix
align-mix:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/DataModified/align_mix.py"

.PHONY: validate-csv-dataset
validate-csv-dataset:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/Validate/validate_csv_dataset.py"
