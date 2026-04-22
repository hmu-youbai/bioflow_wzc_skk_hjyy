# Sandbox Service (Pluggable Repository Edition)

This version keeps the task manager independent from any concrete database.

Supported repositories:
- file
- sqlite
- mysql

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
export REPOSITORY_TYPE=file
uvicorn app.main:app --reload
```

## SQLite

```bash
export REPOSITORY_TYPE=sqlite
export DATABASE_URL=sqlite:///./sandbox_service.db
uvicorn app.main:app --reload
```

## MySQL

```bash
export REPOSITORY_TYPE=mysql
export DATABASE_URL='mysql+pymysql://sandbox_user:password@127.0.0.1:3306/sandbox_service'
uvicorn app.main:app --reload
```
