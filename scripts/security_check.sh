#!/bin/sh

set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

fail() {
    echo "security-check: $1" >&2
    exit 1
}

if [ ! -f ".env.example" ]; then
    fail "missing .env.example template"
fi

for key in ELASTIC_PASSWORD KIBANA_PASSWORD STACK_VERSION CLUSTER_NAME LICENSE ES_PORT KIBANA_PORT ES_MEM_LIMIT KB_MEM_LIMIT LS_MEM_LIMIT ENCRYPTION_KEY; do
    if ! grep -q "^${key}=" ".env.example"; then
        fail ".env.example is missing required key: ${key}"
    fi
done

tracked_env_like=$(
    for path in $(git ls-files | grep -E '(^|/)\.env($|[.])' | grep -vE '(^|/)\.env\.example$' || true); do
        if [ -e "$path" ]; then
            printf '%s\n' "$path"
        fi
    done
)
if [ -n "$tracked_env_like" ]; then
    echo "security-check: tracked secret file(s) found:" >&2
    printf '%s\n' "$tracked_env_like" >&2
    exit 1
fi

tracked_manual_artifacts=$(
    for path in $(git ls-files | grep -E '^tests/manual/(environment_variables\.json|local_artifacts/)' || true); do
        if [ -e "$path" ]; then
            printf '%s\n' "$path"
        fi
    done
)
if [ -n "$tracked_manual_artifacts" ]; then
    echo "security-check: tracked manual secret artifact(s) found:" >&2
    printf '%s\n' "$tracked_manual_artifacts" >&2
    exit 1
fi

dangerous_assignments=$(
    git grep -nE '^(ELASTIC_PASSWORD|KIBANA_PASSWORD|ENCRYPTION_KEY)=' -- . ':(exclude).env.example' || true
)
if [ -n "$dangerous_assignments" ]; then
    echo "security-check: tracked secret assignment(s) found outside .env.example:" >&2
    printf '%s\n' "$dangerous_assignments" >&2
    exit 1
fi

example_defaults=$(
    grep -nE '^(ELASTIC_PASSWORD|KIBANA_PASSWORD)=changeme$|^ENCRYPTION_KEY=[0-9a-fA-F]{64}$' .env.example || true
)
if [ -n "$example_defaults" ]; then
    echo "security-check: .env.example still contains unsafe default secret values:" >&2
    printf '%s\n' "$example_defaults" >&2
    exit 1
fi

echo "security-check: OK"
