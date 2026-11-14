#!/usr/bin/env bash
# Back up GovLens: the PostgreSQL database and uploaded PDFs.
# Qdrant is not backed up: its vectors are rebuilt from PostgreSQL on restore.
#
# Usage: scripts/backup.sh [backup-root]     (default: ./backups)
set -euo pipefail
cd "$(dirname "$0")/.."

root="${1:-backups}"
stamp="$(date +%Y%m%d-%H%M%S)"
target="$root/$stamp"
mkdir -p "$target"

db="${POSTGRES_DB:-govlens}"
user="${POSTGRES_USER:-govlens_user}"

echo "Dumping database $db ..."
docker compose exec -T postgres pg_dump -U "$user" -d "$db" --clean --if-exists --no-owner | gzip > "$target/govlens.sql.gz"

if [ -d data/uploads ]; then
  echo "Archiving uploaded files ..."
  tar -czf "$target/uploads.tar.gz" -C data uploads
fi

gzip -t "$target/govlens.sql.gz"
echo "Backup written to $target"
ls -lh "$target"
