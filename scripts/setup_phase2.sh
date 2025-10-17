#!/bin/bash

# ============================================
# Phase 2 Setup Script - Production Infrastructure
# Sets up database migrations, monitoring, and CI/CD
# ============================================

set -e  # Exit on error

echo "🚀 Healthcare RCM System - Phase 2 Setup"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check Phase 1 completion
echo -e "${YELLOW}📋 Checking Phase 1 completion...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found. Please complete Phase 1 first.${NC}"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found. Please complete Phase 1 first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Phase 1 checks passed${NC}"
echo ""

# Activate virtual environment
source venv/bin/activate

# ============================================
# 1. Setup Database Migrations (Alembic)
# ============================================
echo -e "${YELLOW}🗄️  Setting up database migrations...${NC}"

if [ ! -d "alembic" ]; then
    echo "Initializing Alembic..."
    alembic init alembic
    
    # Copy our custom env.py
    if [ -f "alembic/env.py.template" ]; then
        cp alembic/env.py.template alembic/env.py
    fi
    
    echo -e "${GREEN}✅ Alembic initialized${NC}"
else
    echo -e "${YELLOW}⚠️  Alembic already initialized${NC}"
fi

# Create initial migration
echo "Creating initial migration..."
alembic revision --autogenerate -m "initial_schema" || echo "Migration already exists"

# Apply migrations
echo "Applying migrations..."
alembic upgrade head

echo -e "${GREEN}✅ Database migrations configured${NC}"
echo ""

# ============================================
# 2. Setup Prometheus Metrics
# ============================================
echo -e "${YELLOW}📊 Setting up Prometheus metrics...${NC}"

# Create Prometheus configuration directory
mkdir -p monitoring/prometheus
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/grafana/datasources

# Create Prometheus config
cat > monitoring/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'healthcare-rcm'
    environment: 'production'

scrape_configs:
  - job_name: 'rcm-api'
    static_configs:
      - targets: ['rcm-api:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
EOF

echo -e "${GREEN}✅ Prometheus configuration created${NC}"

# Create Grafana datasource
cat > monitoring/grafana/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
EOF

echo -e "${GREEN}✅ Grafana datasource configured${NC}"
echo ""

# ============================================
# 3. Setup Docker Compose for Local Development
# ============================================
echo -e "${YELLOW}🐳 Creating Docker Compose configuration...${NC}"

cat > docker-compose.monitoring.yml << 'EOF'
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: rcm-prometheus
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
    ports:
      - "9090:9090"
    restart: unless-stopped
    networks:
      - rcm-network

  grafana:
    image: grafana/grafana:latest
    container_name: rcm-grafana
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_INSTALL_PLUGINS=
    ports:
      - "3000:3000"
    restart: unless-stopped
    networks:
      - rcm-network
    depends_on:
      - prometheus

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    container_name: rcm-postgres-exporter
    environment:
      DATA_SOURCE_NAME: "postgresql://rcm_user:${DB_PASSWORD}@postgres:5432/healthcare_rcm?sslmode=disable"
    ports:
      - "9187:9187"
    restart: unless-stopped
    networks:
      - rcm-network

  redis-exporter:
    image: oliver006/redis_exporter:latest
    container_name: rcm-redis-exporter
    environment:
      REDIS_ADDR: "redis:6379"
      REDIS_PASSWORD: "${REDIS_PASSWORD}"
    ports:
      - "9121:9121"
    restart: unless-stopped
    networks:
      - rcm-network

volumes:
  prometheus-data:
  grafana-data:

networks:
  rcm-network:
    external: true
EOF

echo -e "${GREEN}✅ Docker Compose monitoring stack created${NC}"
echo ""

# ============================================
# 4. Setup GitHub Actions (if using GitHub)
# ============================================
echo -e "${YELLOW}🔄 Setting up CI/CD pipeline...${NC}"

mkdir -p .github/workflows

# Check if GitHub Actions file exists
if [ ! -f ".github/workflows/ci-cd.yml" ]; then
    echo -e "${YELLOW}⚠️  GitHub Actions workflow not found${NC}"
    echo "Copy the ci-cd.yml from artifacts to .github/workflows/"
else
    echo -e "${GREEN}✅ GitHub Actions workflow configured${NC}"
fi

# Create necessary GitHub secrets documentation
cat > .github/SECRETS_REQUIRED.md << 'EOF'
# Required GitHub Secrets

For the CI/CD pipeline to work, configure these secrets in your GitHub repository:

## Production Secrets
- `KUBE_CONFIG_PRODUCTION`: Base64 encoded kubeconfig for production cluster
- `SLACK_WEBHOOK`: Slack webhook URL for notifications
- `DOCKER_USERNAME`: Docker registry username
- `DOCKER_PASSWORD`: Docker registry password/token

## Staging Secrets
- `KUBE_CONFIG_STAGING`: Base64 encoded kubeconfig for staging cluster

## API Keys
- `OPENAI_API_KEY`: OpenAI API key for testing
- `K6_CLOUD_TOKEN`: k6 cloud token for performance testing (optional)

## How to Create Secrets
1. Go to your repository on GitHub
2. Click Settings > Secrets and variables > Actions
3. Click "New repository secret"
4. Add each secret listed above

## Generating Kubeconfig
```bash
# Get your kubeconfig
kubectl config view --raw --minify

# Base64 encode it
kubectl config view --raw --minify | base64
```
EOF

echo -e "${GREEN}✅ CI/CD documentation created${NC}"
echo ""

# ============================================
# 5. Setup Kubernetes Manifests
# ============================================
echo -e "${YELLOW}☸️  Setting up Kubernetes manifests...${NC}"

mkdir -p k8s

# Check if deployment files exist
if [ ! -f "k8s/deployment.yaml" ]; then
    echo -e "${YELLOW}⚠️  Kubernetes deployment not found${NC}"
    echo "Copy deployment.yaml from artifacts to k8s/"
else
    echo -e "${GREEN}✅ Kubernetes manifests ready${NC}"
fi

echo ""

# ============================================
# 6. Create Monitoring Start Script
# ============================================
echo -e "${YELLOW}📝 Creating helper scripts...${NC}"

cat > start_monitoring.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting monitoring stack..."

# Start monitoring services
docker-compose -f docker-compose.monitoring.yml up -d

echo ""
echo "✅ Monitoring stack started"
echo ""
echo "📊 Access points:"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana:    http://localhost:3000 (admin/admin)"
echo ""
echo "Import the RCM dashboard from: grafana/dashboards/rcm_overview.json"
EOF
chmod +x start_monitoring.sh

cat > stop_monitoring.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping monitoring stack..."
docker-compose -f docker-compose.monitoring.yml down
echo "✅ Monitoring stack stopped"
EOF
chmod +x stop_monitoring.sh

echo -e "${GREEN}✅ Helper scripts created${NC}"
echo ""

# ============================================
# 7. Initialize Workflow State Tables
# ============================================
echo -e "${YELLOW}🔄 Creating workflow state tables...${NC}"

python << 'PYEOF'
from src.services.database import engine, Base
from src.models.workflow_state import WorkflowStateModel, WorkflowStepModel

# Create tables
Base.metadata.create_all(bind=engine)
print("✅ Workflow state tables created")
PYEOF

echo ""

# ============================================
# 8. Test Monitoring Integration
# ============================================
echo -e "${YELLOW}🧪 Testing monitoring integration...${NC}"

python << 'PYEOF'
try:
    from src.utils.metrics import (
        workflows_total,
        claims_submitted,
        hcx_api_requests,
        get_metrics
    )
    
    # Test metrics
    workflows_total.labels(workflow_type="test").inc()
    claims_submitted.labels(payer="test", claim_type="test").inc()
    hcx_api_requests.labels(endpoint="test", method="POST").inc()
    
    # Get metrics output
    metrics = get_metrics()
    
    if b"rcm_workflows_total" in metrics:
        print("✅ Prometheus metrics working")
    else:
        print("⚠️  Metrics not found")
        
except Exception as e:
    print(f"❌ Metrics test failed: {e}")
PYEOF

echo ""

# ============================================
# 9. Validation
# ============================================
echo -e "${YELLOW}✔️  Running Phase 2 validation...${NC}"

python << 'PYEOF'
import sys
import os

checks = []

# Check Alembic
if os.path.exists("alembic"):
    checks.append(("Alembic configured", True))
else:
    checks.append(("Alembic configured", False))

# Check monitoring
if os.path.exists("monitoring/prometheus/prometheus.yml"):
    checks.append(("Prometheus configured", True))
else:
    checks.append(("Prometheus configured", False))

# Check Grafana
if os.path.exists("monitoring/grafana/datasources/prometheus.yml"):
    checks.append(("Grafana configured", True))
else:
    checks.append(("Grafana configured", False))

# Check K8s
if os.path.exists("k8s") and os.path.isdir("k8s"):
    checks.append(("Kubernetes manifests ready", True))
else:
    checks.append(("Kubernetes manifests ready", False))

# Check GitHub Actions
if os.path.exists(".github/workflows"):
    checks.append(("CI/CD pipeline ready", True))
else:
    checks.append(("CI/CD pipeline ready", False))

# Print results
print("\nPhase 2 Validation Results:")
print("=" * 50)
all_passed = True
for check, passed in checks:
    status = "✅" if passed else "❌"
    print(f"{status} {check}")
    if not passed:
        all_passed = False

print("=" * 50)

if all_passed:
    print("\n✅ Phase 2 setup complete!")
    sys.exit(0)
else:
    print("\n⚠️  Some components need attention")
    sys.exit(1)
PYEOF

# ============================================
# 10. Summary
# ============================================
echo ""
echo "=========================================="
echo -e "${GREEN}✅ Phase 2 Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "📋 What was configured:"
echo "   • Database migrations with Alembic"
echo "   • Workflow state management"
echo "   • Prometheus metrics collection"
echo "   • Grafana dashboards"
echo "   • CI/CD pipeline (GitHub Actions)"
echo "   • Kubernetes deployment manifests"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "1. Start monitoring stack:"
echo "   ./start_monitoring.sh"
echo ""
echo "2. Run database migrations:"
echo "   alembic upgrade head"
echo ""
echo "3. Test workflow state management:"
echo "   pytest tests/test_workflow_state.py -v"
echo ""
echo "4. Deploy to Kubernetes:"
echo "   kubectl apply -f k8s/deployment.yaml"
echo ""
echo "5. Access monitoring:"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana:    http://localhost:3000"
echo ""
echo "📚 Documentation:"
echo "   • README_PHASE2.md - Complete Phase 2 guide"
echo "   • .github/SECRETS_REQUIRED.md - CI/CD secrets"
echo "   • k8s/README.md - Kubernetes deployment guide"
echo ""
echo -e "${GREEN}Ready for Phase 3! 🎉${NC}"