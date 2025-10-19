#!/bin/bash
# ============================================================================
# HealthFlow RCM - Database Restore Script
# Restores database from backup
# ============================================================================

set -e

# Configuration
BACKUP_DIR="/var/backups/healthflow"

# Database configuration
DB_HOST=${POSTGRES_HOST:-postgres}
DB_PORT=${POSTGRES_PORT:-5432}
DB_NAME=${POSTGRES_DB:-healthflow_prod}
DB_USER=${POSTGRES_USER:-healthflow}
DB_PASSWORD=${POSTGRES_PASSWORD}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Check if backup file provided
if [ -z "$1" ]; then
    error "❌ No backup file specified!"
    echo ""
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    ls -lh ${BACKUP_DIR}/healthflow_backup_*.sql.gz* 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE=$1

# Check if file exists
if [ ! -f "${BACKUP_FILE}" ] && [ ! -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    error "❌ Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

# Use full path if not provided
if [ ! -f "${BACKUP_FILE}" ]; then
    BACKUP_FILE="${BACKUP_DIR}/${BACKUP_FILE}"
fi

warning "⚠️  WARNING: This will OVERWRITE the current database!"
warning "⚠️  Database: ${DB_NAME} on ${DB_HOST}:${DB_PORT}"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log "❌ Restore cancelled"
    exit 0
fi

log "🔄 Starting database restore..."

# Decrypt if necessary
TEMP_FILE="${BACKUP_FILE}"
if [ "${BACKUP_FILE##*.}" == "enc" ]; then
    log "🔐 Decrypting backup..."
    
    if [ -z "${ENCRYPTION_KEY}" ]; then
        error "❌ ENCRYPTION_KEY not set!"
        exit 1
    fi
    
    TEMP_FILE="/tmp/restore_temp.sql.gz"
    
    if openssl enc -aes-256-cbc -d \
        -in ${BACKUP_FILE} \
        -out ${TEMP_FILE} \
        -pass pass:${ENCRYPTION_KEY}; then
        log "✅ Backup decrypted"
    else
        error "❌ Decryption failed!"
        exit 1
    fi
fi

# Drop existing connections
log "🔌 Dropping existing database connections..."

export PGPASSWORD="${DB_PASSWORD}"

psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d postgres <<EOF
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = '${DB_NAME}'
  AND pid <> pg_backend_pid();
EOF

# Drop and recreate database
log "🗑️  Dropping existing database..."
psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d postgres <<EOF
DROP DATABASE IF EXISTS ${DB_NAME};
CREATE DATABASE ${DB_NAME};
EOF

# Restore backup
log "📥 Restoring database from backup..."

if gunzip -c ${TEMP_FILE} | psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME}; then
    log "✅ Database restored successfully"
else
    error "❌ Database restore failed!"
    exit 1
fi

# Clean up temporary file
if [ "${TEMP_FILE}" != "${BACKUP_FILE}" ]; then
    rm -f ${TEMP_FILE}
fi

# Run migrations
log "🔄 Running database migrations..."
cd /app
alembic upgrade head

log "🎉 Restore process completed successfully!"

# Verify
log "✅ Verifying restore..."
TABLES=$(psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")

echo ""
echo "============================================"
echo "📊 Restore Summary"
echo "============================================"
echo "Backup File: ${BACKUP_FILE}"
echo "Database: ${DB_NAME}"
echo "Tables Restored: ${TABLES}"
echo "============================================"
