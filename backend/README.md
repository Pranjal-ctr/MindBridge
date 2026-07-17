# Kio Backend API

> AI-Powered Student Wellness & Parenting Platform — FastAPI Backend

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- pip or pipenv

### Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your PostgreSQL credentials

# 5. Create database
# In PostgreSQL:
#   CREATE DATABASE mindbridge;

# 6. Run migrations
alembic upgrade head

# 7. Seed demo data
python -m database.seed

# 8. Start server
uvicorn main:app --reload --port 8000
```

### API Documentation

Once running, visit:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

## Architecture

```
backend/
├── app/                    # FastAPI application modules
│   ├── auth/              # JWT authentication
│   ├── users/             # User profile management
│   ├── conversations/     # ChatGPT-style AI chat
│   ├── memory/            # AI memory system
│   ├── wellness/          # Records, goals, journal
│   ├── risk/              # Risk detection engine
│   ├── parents/           # Parent insights dashboard
│   ├── counselors/        # Session & note management
│   ├── analytics/         # School-wide analytics
│   ├── notifications/     # User notifications
│   ├── subscriptions/     # Billing management
│   └── admin/             # Platform administration
├── database/              # SQLAlchemy models & session
├── migrations/            # Alembic migrations
├── tests/                 # Pytest test suite
└── main.py               # Application entry point
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115 |
| Database | PostgreSQL 15+ (async via asyncpg) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic 1.14 |
| Validation | Pydantic v2 |
| Auth | JWT (python-jose) + bcrypt |
| Testing | pytest + pytest-asyncio + httpx |

## Demo Credentials

After running `python -m database.seed`:

| Role | Email | Password |
|------|-------|----------|
| Student | sarah.johnson@student.rhs.edu | MindBridge2026! |
| Parent | parent.johnson@email.com | MindBridge2026! |
| Counselor | jennifer.martinez@rhs.edu | MindBridge2026! |
| School Admin | admin@rhs.edu | MindBridge2026! |
| Platform Admin | admin@mindbridge.ai | MindBridge2026! |

School Code: `RHS2026`

## Running Tests

```bash
cd backend
pytest tests/ -v
```

## Key Design Decisions

1. **Row-Level Multi-Tenancy**: Every query filters by `tenant_id` from the JWT token
2. **Async Everything**: SQLAlchemy async sessions with asyncpg for non-blocking I/O
3. **Privacy by Design**: Parents never see raw conversations — only aggregated insights
4. **RBAC**: Role-based access via `require_role()` dependency injection
5. **Cursor Pagination**: Messages use cursor-based pagination for real-time chat UX
