# DeligenX — AI-Powered Due Diligence Platform

> Autonomous multi-agent intelligence for deep fundamental analysis, SEC filings, and quality of earnings reports.

## Architecture

```
Frontend (Next.js 16)  →  Backend API (FastAPI)  →  Celery Worker  →  5-Agent AI Pipeline
                                  ↕                        ↕
                             PostgreSQL               Redis (Broker)
                          (Users, Jobs)            (Task Queue, Cache)
```

### The 5-Agent Pipeline

| # | Agent | Purpose |
|---|---|---|
| 1 | **Ingestion** | SEC EDGAR XBRL extraction, financial data normalization |
| 2 | **Analysis** | Ratio engine, trend analysis, fraud detection (Beneish/Altman-Z) |
| 3 | **Market Intelligence** | Competitors, comps valuation, news sentiment, macro data |
| 4 | **Risk Assessment** | 10-module risk scoring with weighted scorecard |
| 5 | **Memo Generation** | 17-section HTML investment memo with 40+ charts |

### Tech Stack

- **Frontend**: Next.js 16, React 19, Tailwind CSS v4, shadcn/ui, Recharts, Framer Motion
- **Backend**: FastAPI, Celery, SQLAlchemy
- **AI/LLM**: Google Vertex AI (Gemini 2.5 Flash/Pro) via LiteLLM
- **Data**: SEC EDGAR API, yfinance, NewsAPI, FRED
- **Databases**: PostgreSQL (platform), SQLite (per-run), ChromaDB (vectors), Redis (cache/broker)
- **Auth**: JWT + HttpOnly cookies + bcrypt
- **Payments**: Stripe (subscription-based credits)

## Local Development Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker Desktop (for PostgreSQL + Redis)
- GCP Service Account key (`deligenx.json`) for Vertex AI

### Quick Start

```bash
# 1. Clone and set up environment
git clone https://github.com/OmDehariya111/deligence.git
cd deligence

# 2. Create Python virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install frontend dependencies
cd frontend && npm install && cd ..

# 5. Set up environment variables
cp .env.example .env
# Edit .env with your real API keys

# 6. Start all services (Windows PowerShell)
.\start_services.ps1

# 7. Start frontend (in a new terminal)
cd frontend
npm run dev
```

The platform will be available at `http://localhost:3000`.

### CLI Usage (Direct Pipeline Execution)

```bash
# Run the full 5-agent pipeline for a ticker
python main.py AAPL --agents full

# Run only the ingestion agent
python main.py MSFT --agents one

# Include a user-provided context file
python main.py TSLA --agents full --file path/to/research.pdf
```

## Deployment

- **Frontend**: Deployed on Vercel
- **Backend**: Deployed on GCP Compute Engine via Docker Compose

See `deploy.sh` for the automated deployment script.

## Project Structure

```
deligence/
├── agents/                  # 5 autonomous AI agents
│   ├── ingestion/           # Agent 1: SEC data extraction
│   ├── analysis/            # Agent 2: Financial analysis
│   ├── market_intelligence/ # Agent 3: Market & competitor data
│   ├── risk_assessment/     # Agent 4: Risk scoring
│   └── memo_generation/     # Agent 5: Report generation
├── api/                     # FastAPI backend
│   ├── main.py              # App entry point
│   ├── routes.py            # Job CRUD endpoints
│   ├── auth_routes.py       # Authentication endpoints
│   ├── celery_app.py        # Background task worker
│   └── models.py            # SQLAlchemy models
├── frontend/                # Next.js frontend
│   └── src/
│       ├── app/             # Pages (home, job, login, admin, etc.)
│       ├── components/      # UI components
│       └── lib/             # Utilities
├── config/                  # Shared configuration
├── mcp_servers/             # MCP data servers (SEC, Market, News, FRED)
├── schemas/                 # Pydantic models
├── utils/                   # Shared utilities
├── tools/                   # Admin tools
├── docs/                    # Workflow documentation
├── tests/                   # Test suites
├── .env.example             # Environment variables template
├── crew.py                  # CrewAI orchestration
├── main.py                  # CLI entry point
├── requirements.txt         # Python dependencies
├── Dockerfile.backend       # Backend Docker image
├── docker-compose.yml       # Local dev services (Redis + PostgreSQL)
├── docker-compose.prod.yml  # Production deployment
├── deploy.sh                # Cloud deployment script
└── start_services.ps1       # Local dev startup script (Windows)
```

## License

Proprietary — All rights reserved.
