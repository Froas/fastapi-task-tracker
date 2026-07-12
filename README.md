# 🚀Roadmap Tracker FastAPI Backend

A modern backend API built with [FastAPI](https://fastapi.tiangolo.com/) and Python for the **TaskNest Roadmap Tracker**.
This backend is designed to power the [TaskNest frontend](https://github.com/Froas/next-react-tasknest) — a project management/roadmap tracking tool.

* **Dependency management**: [pipenv](https://pipenv.pypa.io/en/latest/)
* **Database migrations**: [Alembic](https://alembic.sqlalchemy.org/en/latest/)

---

## 🛠️ Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/Froas/next-react-tasknest.git
cd fastapi-task-tracker
```

### 2. Setup Virtual Environment

```bash
pipenv shell
```

### 3. Install Dependencies

```bash
pipenv install --dev
```

**Initialize Alembic (First Time Only):**

```bash
alembic upgrade head
```


### 🚦 Running the Application

Make sure your `.env` file is configured (see example below).

```bash
uvicorn main:app --reload
```

* Change `main:app` if your entrypoint or FastAPI instance is named differently.
* `--reload` enables live code reloading for development.

### 🔑 Resetting a Local User Password

Passwords are stored as bcrypt hashes and cannot be recovered. To set a new
password while preserving the user's tasks and other data, run this command
from the backend directory:

```bash
pipenv run python -c 'from sqlmodel import Session,select; from db import engine; from models import User; s=Session(engine); u=s.exec(select(User).where(User.username=="naruto")).one(); u.set_password("naruto"); s.add(u); s.commit()'
```

Afterward, sign in with username `naruto` and password `naruto`.
Replace both values in the command when resetting another user or choosing a
different password. Restart the backend if it is already running.

### 🗄️ Database Migrations (Alembic)

**Initialize Alembic (First Time Only):**

```bash
alembic init alembic
```

**Configure Alembic**

* Edit `alembic.ini` and `alembic/env.py` to set your database URL (see the .env example below).

**Creating a Migration:**

```bash
alembic revision --autogenerate -m "Describe your migration"
```

**Applying Migrations:**

```bash
alembic upgrade head
```

---

## 📄 Environment Variables

Create a `.env` file in your project root with the following keys:

```env
```bash
ACCESS_TOKEN_EXPIRE_MINUTES=
SECRET_KEY=
ALGORITHM=
GOOGLE_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
REDIRECT=
```

---

## 🏗️ What This Backend Does

* Provides RESTful API endpoints for TaskNest roadmap tracker frontend ([repo link](https://github.com/Froas/next-react-tasknest))
* Handles user authentication via JWT tokens
* Integrates with Google OAuth (see `GOOGLE_CLIENT_*` env vars)
* Provides endpoints for tasks, roadmaps, and user management
* Planned: Redis integration for TODO tasks
* Planned: Google Calendar & other calendar API endpoints
* Planned: Telegram bot endpoint

---

## 🧑‍💻 Tech Stack

* **Backend:** FastAPI, Python
* **Web server:** Uvicorn
* **Auth:** JWT
* **Database:** Your choice (configured via Alembic, SQLAlchemy, and env)
* **Planned:** Redis, Google Calendar API, Telegram Bot

---

## 📝 TODOs

* [ ] Redis integration for fast TODO operations
* [ ] Google Calendar endpoint
* [ ] Other calendar API endpoints
* [ ] Telegram bot endpoint

---

## 🙌 Feedback & Contributions

Contributions, issues, and feature requests are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/YourFeature`)
3. Commit your changes (`git commit -m 'Add YourFeature'`)
4. Push to the branch (`git push origin feature/YourFeature`)
5. Open a Pull Request

Thanks for helping make TaskNest better! 🚀
```
