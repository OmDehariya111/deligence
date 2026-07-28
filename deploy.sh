#!/bin/bash
set -e

echo "==============================================="
echo "🚀 DELIGENX BACKEND DEPLOYMENT SCRIPT"
echo "   Frontend is on Vercel — this deploys the"
echo "   backend (FastAPI + Celery + Redis + Postgres)"
echo "==============================================="

# ─── Step 1: Install Docker ─────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "[1/3] Docker not found. Installing Docker..."
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg

    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Allow current user to run Docker without sudo
    sudo usermod -aG docker $USER
    echo "✅ Docker installed. You may need to log out and back in for group changes."
else
    echo "[1/3] Docker already installed ✅"
fi

# ─── Step 2: Verify required files ──────────────────────────
echo "[2/3] Checking required files..."

if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ Error: docker-compose.prod.yml not found."
    echo "   Run this script from inside the Deligence project folder."
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found."
    echo "   Copy .env.example to .env and fill in your real API keys:"
    echo "   cp .env.example .env && nano .env"
    exit 1
fi

if [ ! -f "deligenx.json" ]; then
    echo "⚠️  Warning: deligenx.json (GCP service account key) not found."
    echo "   Vertex AI LLM calls will fail without it."
    echo "   Upload it with: scp deligenx.json <user>@<vm-ip>:~/deligence/"
    echo ""
fi

echo "   All required files present ✅"

# ─── Step 3: Build and deploy ────────────────────────────────
echo "[3/3] Building and launching containers..."
sudo docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "==============================================="
echo "✅ BACKEND DEPLOYMENT COMPLETE!"
echo ""
echo "Services running:"
echo "  • FastAPI Backend  →  http://$(curl -s ifconfig.me):8000"
echo "  • Celery Worker    →  Processing background tasks"
echo "  • PostgreSQL       →  User accounts & job data"
echo "  • Redis            →  Task queue & API cache"
echo ""
echo "Health check:"
echo "  curl http://localhost:8000/"
echo ""
echo "View logs:"
echo "  sudo docker compose -f docker-compose.prod.yml logs -f"
echo "==============================================="
