#!/bin/sh

set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
ENV_FILE="$ROOT_DIR/.env"
EXAMPLE_FILE="$ROOT_DIR/.env.example"

if [ ! -f "$EXAMPLE_FILE" ]; then
    echo "init-local-env: missing template: $EXAMPLE_FILE" >&2
    exit 1
fi

if [ -e "$ENV_FILE" ]; then
    echo "init-local-env: $ENV_FILE already exists; refusing to overwrite it" >&2
    exit 1
fi

random_secret() {
    LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24
}

random_hex() {
    od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

elastic_password=$(random_secret)
kibana_password=$(random_secret)
encryption_key=$(random_hex)

umask 077
cp "$EXAMPLE_FILE" "$ENV_FILE"

tmp_file="$ENV_FILE.tmp"
sed \
    -e "s/^ELASTIC_PASSWORD=.*/ELASTIC_PASSWORD=$elastic_password/" \
    -e "s/^KIBANA_PASSWORD=.*/KIBANA_PASSWORD=$kibana_password/" \
    -e "s/^ENCRYPTION_KEY=.*/ENCRYPTION_KEY=$encryption_key/" \
    "$ENV_FILE" >"$tmp_file"
mv "$tmp_file" "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "init-local-env: created $ENV_FILE with random local-only secrets"
echo "init-local-env: rotate any previously exposed secrets before using ELK again"
