# Apex Monitor — Claude Code Guide

## Project Overview

Apex Monitor is an AI-powered network monitoring tool. It polls devices via ICMP, SNMP (v3), TCP port checks, and SSH; stores metrics in InfluxDB; and exposes a REST API via FastAPI. A React frontend visualises device health and alerts.

## Repository Layout

```
apex-monitor/
├── backend/
│   ├── main.py            # FastAPI app entry point — binds to 127.0.0.1 only
│   ├── config.yaml        # Device inventory (excluded from Git)
│   ├── .env.template      # Safe-to-commit secrets template
│   ├── .gitignore
│   ├── SECURITY.md
│   ├── requirements.txt
│   ├── scheduler.py       # APScheduler — registers periodic monitor jobs
│   ├── monitors/
│   │   ├── icmp.py        # Ping / latency checks
│   │   ├── snmp.py        # SNMPv3 GET/WALK
│   │   ├── port_check.py  # TCP connect checks
│   │   └── ssh_check.py   # SSH key-based connectivity check
│   ├── db/
│   │   └── influx.py      # InfluxDB client wrapper (reads creds from env)
│   └── api/
│       └── routes.py      # FastAPI route definitions
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   │       ├── Dashboard.jsx
│   │       ├── DeviceCard.jsx
│   │       └── AlertBanner.jsx
│   └── package.json
└── docker-compose.yml     # InfluxDB + backend, both bound to localhost
```

## Development Setup

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.template .env          # then fill in real values — never commit .env
python main.py

# Frontend
cd frontend
npm install
npm start
```

## Security Rules

- **Never** hardcode credentials or secrets anywhere in source code.
- All secrets live in `backend/.env` (not committed).
- FastAPI must always bind to `host="127.0.0.1"` in `main.py` and in `docker-compose.yml`.
- InfluxDB port mapping must always be `127.0.0.1:8086:8086`.
- Prefer SNMPv3 (SHA auth + AES privacy) over v1/v2c.
- SSH monitoring uses key-based auth only — no passwords.
- See `backend/SECURITY.md` for the full policy.

## Phase Roadmap

| Phase | Scope |
|-------|-------|
| 1.1 | Project scaffolding (current) |
| 1.2 | ICMP + port check implementation |
| 1.3 | SNMP v3 polling |
| 2 | InfluxDB write/query layer |
| 3 | Frontend dashboard |
| 4 | JWT authentication for API |
| 5 | AI anomaly detection (Anthropic API) |

## Coding Conventions

- Python: follow PEP 8; no credentials in source files.
- Each monitor module exposes a single `check()` function returning a `dict`.
- All InfluxDB credentials read from `os.environ` in `db/influx.py` — never passed as arguments from calling code.
- Frontend components are functional React with hooks; no class components.
