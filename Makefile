ROOT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
DOCKER_COMPOSE_PROJECT_NAME := $(notdir $(patsubst %/,%,$(ROOT_DIR)))
VENV_PYTHON := $(ROOT_DIR)/.venv/bin/python
PYENV_BIN := $(HOME)/.pyenv/bin/pyenv
BOOTSTRAP_PYTHON := $(shell if [ -x "$(PYENV_BIN)" ] && [ -f "$(ROOT_DIR)/.python-version" ]; then "$(PYENV_BIN)" which python 2>/dev/null; elif command -v python3.11 >/dev/null 2>&1; then command -v python3.11; elif command -v python >/dev/null 2>&1; then command -v python; else command -v python3; fi)

ifneq ($(wildcard $(VENV_PYTHON)),)
PYTHON ?= $(VENV_PYTHON)
else
PYTHON ?= python3
endif

SCHEMA ?= zeek
PCAP_TO_LOG_ARGS ?=
LOG_TO_CSV_ARGS ?=
PCAP_TO_CSV_ARGS ?=
FEATURE_EXPORT_ARGS ?=
COWRIE_DOCKER_COMPOSE := docker compose -p adids-cowrie -f "$(ROOT_DIR)/docker-compose.cowrie.yml"
DEMO_DOCKER_COMPOSE := docker compose -p adids-demo -f "$(ROOT_DIR)/docker-compose.demo.yml"
KIBANA_COWRIE_LIVE_DASHBOARD_NDJSON := $(ROOT_DIR)/docs/kibana_saved_objects/cowrie_live_attack_monitoring.ndjson
ES_COWRIE_LIVE_ENRICH_PIPELINE_JSON := $(ROOT_DIR)/filebeat/cowrie_live_enrich_pipeline.json
ES_COWRIE_LIVE_ENRICH_PIPELINE_ID := zeek-cowrie-live-enrich-v1

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

.PHONY: elk-up
elk-up:
	@docker compose up -d setup es01 kibana filebeat01

.PHONY: elk-up-simulation
elk-up-simulation:
	@docker compose up -d setup es01 kibana filebeat01 filebeat-sim01

.PHONY: elk-up-cowrie
elk-up-cowrie:
	@docker compose up -d setup es01 kibana filebeat-cowrie01

.PHONY: elk-up-cowrie-live
elk-up-cowrie-live:
	@ES01_CID="$$(docker ps -a --filter label=com.docker.compose.project=$(DOCKER_COMPOSE_PROJECT_NAME) --filter label=com.docker.compose.service=es01 -q)"; \
	if [ -n "$$ES01_CID" ]; then \
		docker compose up -d --no-deps es01 kibana filebeat-cowrie01; \
	else \
		docker compose up -d setup es01 kibana filebeat-cowrie01; \
	fi
	@$(MAKE) es-put-cowrie-live-enrich-pipeline
	@docker compose up -d --no-deps --force-recreate filebeat-cowrie-live01

.PHONY: elk-down
elk-down:
	@docker compose down

.PHONY: elk-ps
elk-ps:
	@docker compose ps

.PHONY: es-put-cowrie-live-enrich-pipeline
es-put-cowrie-live-enrich-pipeline:
	@if [ ! -f "$(ES_COWRIE_LIVE_ENRICH_PIPELINE_JSON)" ]; then \
		echo "Pipeline file not found: $(ES_COWRIE_LIVE_ENRICH_PIPELINE_JSON)" >&2; \
		exit 1; \
	fi
	@set -a; . "$(ROOT_DIR)/.env"; set +a; \
	curl -k --fail-with-body -sS \
		-u "elastic:$$ELASTIC_PASSWORD" \
		"https://localhost:$${ES_PORT:-9200}/_cluster/health?wait_for_status=yellow&timeout=90s" >/dev/null; \
	curl -k --fail-with-body -sS \
		-u "elastic:$$ELASTIC_PASSWORD" \
		-H "Content-Type: application/json" \
		-X PUT "https://localhost:$${ES_PORT:-9200}/_ingest/pipeline/$(ES_COWRIE_LIVE_ENRICH_PIPELINE_ID)" \
		--data-binary @"$(ES_COWRIE_LIVE_ENRICH_PIPELINE_JSON)"

.PHONY: kibana-import-cowrie-live-dashboard
kibana-import-cowrie-live-dashboard:
	@if [ ! -f "$(KIBANA_COWRIE_LIVE_DASHBOARD_NDJSON)" ]; then \
		echo "Saved Objects file not found: $(KIBANA_COWRIE_LIVE_DASHBOARD_NDJSON)" >&2; \
		exit 1; \
	fi
	@set -a; . "$(ROOT_DIR)/.env"; set +a; \
	curl --fail-with-body -sS \
		-u "elastic:$$ELASTIC_PASSWORD" \
		"http://localhost:$${KIBANA_PORT:-5601}/api/status" >/dev/null; \
	curl --fail-with-body -sS \
		-u "elastic:$$ELASTIC_PASSWORD" \
		-H "kbn-xsrf: true" \
		-X POST "http://localhost:$${KIBANA_PORT:-5601}/api/saved_objects/_import?overwrite=true" \
		--form file=@"$(KIBANA_COWRIE_LIVE_DASHBOARD_NDJSON)"

.PHONY: cowrie-up
cowrie-up:
	@mkdir -p "$(ROOT_DIR)/cowrie/var/log/cowrie" "$(ROOT_DIR)/cowrie/var/lib/cowrie"
	@chmod 0777 "$(ROOT_DIR)/cowrie/var/log/cowrie" "$(ROOT_DIR)/cowrie/var/lib/cowrie"
	@$(COWRIE_DOCKER_COMPOSE) up -d

.PHONY: cowrie-live-up
cowrie-live-up:
	@mkdir -p "$(ROOT_DIR)/cowrie/var/log/cowrie" "$(ROOT_DIR)/cowrie/var/lib/cowrie" "$(ROOT_DIR)/data/logs/zeek/live/cowrie/current"
	@chmod 0777 "$(ROOT_DIR)/cowrie/var/log/cowrie" "$(ROOT_DIR)/cowrie/var/lib/cowrie" "$(ROOT_DIR)/data/logs/zeek/live/cowrie/current"
	@$(COWRIE_DOCKER_COMPOSE) up -d cowrie zeek-cowrie-live

.PHONY: cowrie-down
cowrie-down:
	@$(COWRIE_DOCKER_COMPOSE) down

.PHONY: cowrie-ps
cowrie-ps:
	@$(COWRIE_DOCKER_COMPOSE) ps

.PHONY: run
run:
	@cd "$(ROOT_DIR)/src/main" && "$(PYTHON)" -m Simulation.run

.PHONY: run-live
run-live:
	@cd "$(ROOT_DIR)/src/main" && "$(PYTHON)" -m Live.run

.PHONY: prepare-live-demo-model
prepare-live-demo-model:
	@cd "$(ROOT_DIR)/src/main" && "$(PYTHON)" -m Live.prepare_demo_model

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
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/FeatureExtract/Zeek/pcap_to_log_extractor.py" $(PCAP_TO_LOG_ARGS)

.PHONY: log-to-csv
log-to-csv:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/FeatureExtract/Zeek/log_to_csv_extractor.py" $(LOG_TO_CSV_ARGS)

.PHONY: pcap-to-csv
pcap-to-csv:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/FeatureExtract/Zeek/pcap_to_csv_pipeline.py" $(PCAP_TO_CSV_ARGS)

.PHONY: feature-export
feature-export:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/FeatureExtract/Zeek/feature_exporter.py" $(FEATURE_EXPORT_ARGS)

.PHONY: demo-live-up
demo-live-up:
	@mkdir -p "$(ROOT_DIR)/data/logs/zeek/live/local_iot/current" "$(ROOT_DIR)/data/csv/live/local_iot_demo" "$(ROOT_DIR)/data/live/state"
	@$(DEMO_DOCKER_COMPOSE) up -d --build

.PHONY: demo-live-reset
demo-live-reset:
	@/bin/sh "$(ROOT_DIR)/demo/reset_live_demo_state.sh"

.PHONY: demo-live-down
demo-live-down:
	@$(DEMO_DOCKER_COMPOSE) down

.PHONY: demo-live-ps
demo-live-ps:
	@$(DEMO_DOCKER_COMPOSE) ps

.PHONY: demo-live-inject-alert
demo-live-inject-alert:
	@/bin/sh "$(ROOT_DIR)/demo/inject_live_demo_conn_log.sh"

.PHONY: align-mix
align-mix:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/DataModified/align_mix.py"

.PHONY: validate-csv-dataset
validate-csv-dataset:
	@"$(PYTHON)" "$(ROOT_DIR)/src/util/Validate/validate_csv_dataset.py"
