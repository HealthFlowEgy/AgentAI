#!/bin/bash
# ============================================================================
# HealthFlow RCM - Database Backup Script
# Creates encrypted backups and uploads to S3
# ============================================================================

set -e

# Configuration
BACKUP_DIR="/var/backups/healthflow"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="healthflow_backup_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}

# Database configuration
DB_HOST=${POSTGRES_HOST:-postgres}
DB_PORT=${POSTGRES_PORT:-5432}
DB_NAME=${POSTGRES_DB:-healthflow_prod}
DB_USER=${POSTGRES_USER:-healthflow}
DB_PASSWORD=${POSTGRES_PASSWORD}

# S3 configuration (optional)
S3_BUCKET=${S3_BUCKET:-}
AWS_REGION=${AWS_REGION:-us-east-1}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Create backup directory
mkdir -p ${BACKUP_DIR}

log "🔄 Starting database backup..."

# Perform backup
log "📦 Backing up database ${DB_NAME}..."

export PGPASSWORD="${DB_PASSWORD}"

if pg_dump -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} \
    --format=plain \
    --no-owner \
    --no-acl \
    --verbose \
    | gzip > ${BACKUP_DIR}/${BACKUP_FILE}; then
    
    log "✅ Database backup completed: ${BACKUP_FILE}"
    
    # Get backup size
    BACKUP_SIZE=$(du -h ${BACKUP_DIR}/${BACKUP_FILE} | cut -f1)
    log "📊 Backup size: ${BACKUP_SIZE}"
else
    error "❌ Database backup failed!"
    exit 1
fi

# Encrypt backup (optional)
if [ ! -z "${ENCRYPTION_KEY}" ]; then
    log "🔐 Encrypting backup..."
    
    openssl enc -aes-256-cbc -salt \
        -in ${BACKUP_DIR}/${BACKUP_FILE} \
        -out ${BACKUP_DIR}/${BACKUP_FILE}.enc \
        -pass pass:${ENCRYPTION_KEY}
    
    if [ $? -eq 0 ]; then
        log "✅ Backup encrypted successfully"
        rm ${BACKUP_DIR}/${BACKUP_FILE}
        BACKUP_FILE="${BACKUP_FILE}.enc"
    else
        error "❌ Encryption failed!"
    fi
fi

# Upload to S3 (optional)
if [ ! -z "${S3_BUCKET}" ]; then
    log "☁️  Uploading backup to S3..."
    
    if aws s3 cp ${BACKUP_DIR}/${BACKUP_FILE} \
        s3://${S3_BUCKET}/backups/database/${BACKUP_FILE} \
        --region ${AWS_REGION} \
        --storage-class STANDARD_IA; then
        
        log "✅ Backup uploaded to S3: s3://${S3_BUCKET}/backups/database/${BACKUP_FILE}"
    else
        error "❌ S3 upload failed!"
    fi
fi

# Clean up old backups
log "🧹 Cleaning up old backups (older than ${RETENTION_DAYS} days)..."

find ${BACKUP_DIR} -name "healthflow_backup_*.sql.gz*" \
    -type f -mtime +${RETENTION_DAYS} -delete

OLD_BACKUPS_COUNT=$(find ${BACKUP_DIR} -name "healthflow_backup_*.sql.gz*" -type f | wc -l)
log "📊 ${OLD_BACKUPS_COUNT} backup(s) retained locally"

# Verify backup
log "✅ Verifying backup integrity..."

if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    if [ "${BACKUP_FILE##*.}" == "enc" ]; then
        # Verify encrypted file
        if openssl enc -aes-256-cbc -d \
            -in ${BACKUP_DIR}/${BACKUP_FILE} \
            -pass pass:${ENCRYPTION_KEY} \
            | gzip -t; then
            log "✅ Backup verification successful"
        else
            error "❌ Backup verification failed!"
            exit 1
        fi
    else
        # Verify compressed file
        if gzip -t ${BACKUP_DIR}/${BACKUP_FILE}; then
            log "✅ Backup verification successful"
        else
            error "❌ Backup verification failed!"
            exit 1
        fi
    fi
else
    error "❌ Backup file not found!"
    exit 1
fi

log "🎉 Backup process completed successfully!"

# Summary
echo ""
echo "============================================"
echo "📊 Backup Summary"
echo "============================================"
echo "Backup File: ${BACKUP_FILE}"
echo "Backup Size: ${BACKUP_SIZE}"
echo "Location: ${BACKUP_DIR}/${BACKUP_FILE}"
if [ ! -z "${S3_BUCKET}" ]; then
    echo "S3 Location: s3://${S3_BUCKET}/backups/database/${BACKUP_FILE}"
fi
echo "Retention: ${RETENTION_DAYS} days"
echo "============================================"
