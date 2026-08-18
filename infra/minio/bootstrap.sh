#!/bin/sh

set -eu

alias_name="vietreceipt-local"

: "${STORAGE_ENDPOINT:?STORAGE_ENDPOINT is required}"
: "${STORAGE_ACCESS_KEY:?STORAGE_ACCESS_KEY is required}"
: "${STORAGE_SECRET_KEY:?STORAGE_SECRET_KEY is required}"
: "${STORAGE_BUCKET:?STORAGE_BUCKET is required}"

mc alias set "$alias_name" "$STORAGE_ENDPOINT" "$STORAGE_ACCESS_KEY" "$STORAGE_SECRET_KEY"
mc ready "$alias_name"
mc mb --ignore-existing "$alias_name/$STORAGE_BUCKET"
mc anonymous set none "$alias_name/$STORAGE_BUCKET"
mc stat "$alias_name/$STORAGE_BUCKET"

echo "MinIO bucket '$STORAGE_BUCKET' is ready and private."
