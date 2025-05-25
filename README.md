# 🚀 FastAPI Project

A modern backend API built with [FastAPI](https://fastapi.tiangolo.com/) and Python.  
Dependency management is handled with [pipenv](https://pipenv.pypa.io/en/latest/), and database migrations are managed by [Alembic](https://alembic.sqlalchemy.org/en/latest/).

---

## 🛠️ Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/Froas/next-react-tasknest.git
cd fastapi-task-tracker
```

2. Setup Virtual Environment

```bash
pipenv shell
```

3. Install Dependencies

```bash
pipenv install --dev
```

🚦 Running the Application

Make sure your .env file is configured (see example below).

```bash
uvicorn main:app --reload
```
    Change main:app if your entrypoint or FastAPI instance is named differently.
    --reload enables live code reloading for development.

🗄️ Database Migrations (Alembic)
Initialize Alembic (First Time Only)

```bash
alembic init alembic
```

Configure Alembic

    Edit alembic.ini and alembic/env.py to set your database URL (see the .env example below).

Creating a Migration

```bash
alembic revision --autogenerate -m "Describe your migration"
```

Applying Migrations

```bash
alembic upgrade head
```

📄 Environment Variables

Create a .env file in your project root:

```bash
ACCESS_TOKEN_EXPIRE_MINUTES = 300
SECRET_KEY=09d25e094faf7099f6f0f4caa6cf63b88e8d3e7
ALGORITHM=HS256
```