#!/usr/bin/env bash
# Restore a GovLens backup made by scripts/backup.sh.
# This REPLACES the current database and uploads. Vectors are rebuilt
# automatically when the app starts (startup reconciliation).
#
# Usage: scripts/restore.sh backups/<timestamp> [--yes]
set -euo pipefail
cd "$(dirname "$0")/.."

source_dir="${1:?Usage: scripts/restore.sh backups/<timestamp> [--yes]}"
[ -f "$source_dir/govlens.sql.gz" ] || { echo "No govlens.sql.gz in $source_dir" >&2; exit 1; }

if [ "${2:-}" != "--yes" ]; then
  read -r -p "Replace the current GovLens database and uploads with $source_dir? [y/N] " answer
  [ "$answer" = "y" ] || [ "$answer" = "Y" ] || { echo "Cancelled."; exit 1; }
fi

db="${POSTGRES_DB:-govlens}"
user="${POSTGRES_USER:-govlens_user}"

echo "Stopping the app ..."
docker compose stop app
echo "Restoring database $db ..."
gunzip -c "$source_dir/govlens.sql.gz" | docker compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U "$user" -d "$db" > /dev/null

if [ -f "$source_dir/uploads.tar.gz" ]; then
  echo "Restoring uploaded files ..."
  rm -rf data/uploads
  mkdir -p data
  tar -xzf "$source_dir/uploads.tar.gz" -C data
fi

echo "Clearing vectors (they are rebuilt from the database) ..."
curl -fsS -X DELETE "http://localhost:${QDRANT_PORT:-6333}/collections/${QDRANT_COLLECTION:-government_documents}" > /dev/null || true

echo "Starting the app (it rebuilds vectors in the background) ..."
docker compose start app
echo "Restore complete. Check: curl http://localhost:8000/api/v1/health/ready"
