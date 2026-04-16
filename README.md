<h1 align="center">♻️ GreenCycle Nexus</h1>
<h3 align="center">Smart Waste Management System</h3>

<p align="center">
  <img src="https://img.shields.io/badge/Backend-Flask-black?style=for-the-badge&logo=flask" />
  <img src="https://img.shields.io/badge/Frontend-HTML%2FCSS%2FJS-blue?style=for-the-badge&logo=html5" />
  <img src="https://img.shields.io/badge/Database-SQLite-003B57?style=for-the-badge&logo=sqlite" />
  <img src="https://img.shields.io/badge/Auth-Bearer%20Token-green?style=for-the-badge" />
</p>

---

## 🧠 Overview

```
GreenCycle Nexus is a government-style waste management system designed to streamline waste logging,
approval workflows, and payment tracking. It simulates a real-world civic system with role-based access.
```

---

## 🚀 Features

```
- Multi-role system: Admin, Citizen, Worker
- Waste logging and approval workflow
- Automatic payment generation
- Pickup scheduling system
- Dashboard analytics (approval rate, waste mix)
- Light/Dark theme toggle
```

---

## 🛠️ Tech Stack

<p align="center">
  <img src="https://skillicons.dev/icons?i=python,flask,html,css,js,sqlite" height="50"/>
</p>

```
Backend: Python + Flask
Frontend: HTML, CSS, JavaScript (SPA)
Database: SQLite
Authentication: Bearer Token
```

---

## 📁 Project Structure

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

---

## ⚙️ Installation & Setup

### Backend (Windows)

```powershell
cd greencycle-nexus\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

```
Backend URL: http://127.0.0.1:5000
```

---

### Frontend

```text
Option 1: Open app.html directly in browser

Option 2:
cd ..
python -m http.server 5500
Open http://127.0.0.1:5500/app.html
```

---

## 👥 Demo Accounts

```text
Admin    → Phone: 9000000001 | PIN: 1111
Citizen  → Phone: 9000000002 | PIN: 2222
Worker   → Phone: 9000000003 | PIN: 3333
```

---

## 📊 Business Rules

### Waste Pricing

```text
Food     → ₹2 / kg
Plastic  → ₹3 / kg
Other    → ₹1 / kg
```

### Workflow

```text
Citizen logs waste → Admin approves → Payment generated → Worker collects
```

---

## 🔗 API Endpoints

```text
POST   /register              → Register user
POST   /login                 → Login
POST   /waste                 → Log waste
GET    /history/:user_id      → User history
GET    /pending               → Admin pending list
POST   /approve/:id           → Approve entry
GET    /payments/:user_id     → Payments
GET    /schedule/:user_id     → Pickup schedule
GET    /pickups/:worker_id    → Worker pickups
POST   /collect/:id           → Mark collected
```

---

## 📊 Highlights

```
- Role-based workflow system
- Real-world civic problem simulation
- Full backend + frontend integration
- Automated payment logic
- Dashboard analytics
```

---

## 🔥 Future Improvements

```
- Add timeline-based charts
- Filtering and export options
- OTP authentication
- Payment gateway integration
- Cloud deployment
```

---

## 💣 One-Line Summary

```
A role-based waste management system that automates logging, approval,
payment, and collection workflows.
```

---

## 👨‍💻 Author

```text
Muhammed Salman N
Email: muhammedsalmanbinnoor@gmail.com
GitHub: https://github.com/mav8stro
```

---

## 📄 License

```text
MIT License
```
