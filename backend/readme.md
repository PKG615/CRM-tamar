# CRM Portal Backend

FastAPI + PostgreSQL backend for the CRM Portal.

This backend is already implemented. This document explains how to
set up and run the existing backend on a new developer system.

---

## 1. Technology Stack

| Technology | Purpose |
| ------------ | --------- |
| Python | Backend programming language |
| FastAPI | REST API framework |
| Uvicorn | ASGI application server |
| PostgreSQL | Relational database |
| SQLAlchemy | ORM |
| Psycopg 3 | PostgreSQL driver |
| Alembic | Database migrations |
| Pydantic | Data validation |
| Pydantic Settings | Environment configuration |
| JWT | Authentication |
| Argon2 | Password hashing |

---

## 2. Requirements

Before starting, install the following:

- Python 3.x
- PostgreSQL 18
- Git

Recommended:

- pgAdmin 4
- VS Code

Verify Python:

```powershell
python --version




cd backend
python -m venv venv
.\venv\Scripts\Activate
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
alembic current
uvicorn app.main:app --reload