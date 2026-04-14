# GreenCycle Nexus

A government-style waste management demo app with:
- role-based login (`admin`, `citizen`, `worker`)
- waste logging and approval workflow
- payment tracking and pickup schedule
- light/dark theme toggle
- dashboard visualizations (approval rate and waste mix)

## Project Structure

```text
greencycle-nexus/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── routes.py
│   ├── requirements.txt
│   └── run.py
└── app.html
```

## Quick Start (Windows)

### 1) Run backend

```powershell
cd greencycle-nexus\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Backend URL: `http://127.0.0.1:5000`

Notes:
- SQLite database is created automatically on first run.
- Demo users are available immediately.

### 2) Run frontend

You can use any one of these:

1. Open file directly:
   - Open `greencycle-nexus\app.html` in browser.
2. Python static server:
   ```powershell
   cd ..   # back to greencycle-nexus
   python -m http.server 5500
   ```
   then open `http://127.0.0.1:5500/app.html`
3. Live Server extension in Cursor/VS Code:
   - Right-click `app.html` -> Open with Live Server

## Demo Accounts

| Role | Phone | PIN |
|------|-------|-----|
| Admin | `9000000001` | `1111` |
| Citizen | `9000000002` | `2222` |
| Worker | `9000000003` | `3333` |

## Business Rules

### Waste Pricing

| Type | Rate |
|------|------|
| Food | `₹2 / kg` |
| Plastic | `₹3 / kg` |
| Other | `₹1 / kg` |

### Workflow

Citizen logs waste -> Admin approves entry -> Payment is auto-generated.

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/register` | No | Register user |
| POST | `/login` | No | Login and return token |
| POST | `/waste` | Bearer | Log waste entry |
| GET | `/history/:user_id` | Bearer | User waste history |
| GET | `/pending` | Admin | Pending entries |
| POST | `/approve/:id` | Admin | Approve entry and create payment |
| GET | `/payments/:user_id` | Bearer | User payments and total due |
| GET | `/schedule/:user_id` | Bearer | Pickup schedule |
| GET | `/pickups/:worker_id` | Bearer | Worker pickups |
| POST | `/collect/:id` | Bearer | Mark pickup as collected |

## Tech Stack

- Frontend: Single-page HTML/CSS/JS
- Backend: Python + Flask
- Database: SQLite
- Auth: Bearer token (stored in localStorage)

## Next Improvements

- Add charts with timeline trends
- Add filtering and export in history
- Add OTP login and stronger auth controls
- Add payment gateway integration
