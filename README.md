# Study App API

REST API for user registration and related domain logic. Built with **FastAPI**, **SQLAlchemy 2**, **Alembic**, and **SQLite**, with configuration from environment variables and request/response validation via **Pydantic v2**.

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Running the server](#running-the-server)
- [API documentation (Swagger)](#api-documentation-swagger)
- [HTTP endpoints](#http-endpoints)
- [Database and migrations](#database-and-migrations)
- [Project documentation (HTML & UML)](#project-documentation-html--uml)
- [Makefile reference](#makefile-reference)
- [Git](#git)

---

## Features

- Environment-based config (`.env` + `python-dotenv`)
- Layered structure: routers → services → repositories → ORM models
- Alembic migrations for schema evolution
- OpenAPI / Swagger UI out of the box
- Pydantic validation on API payloads

---

## Tech stack

| Layer        | Technology                          |
| ------------ | ----------------------------------- |
| Web framework| FastAPI                             |
| ASGI server  | Uvicorn                             |
| ORM          | SQLAlchemy 2.x                      |
| Migrations   | Alembic                             |
| Database     | SQLite (file path from env)         |
| Validation   | Pydantic v2                         |
| HTTP client (dev) | httpx (for TestClient)       |

---

## Repository layout

```text
study_app/
├── app/
│   ├── main.py              # FastAPI app factory & routers
│   ├── api/v1/              # HTTP routers (handlers)
│   ├── core/                # Settings, DB session
│   ├── models/
│   │   ├── core/            # Core domain entities (e.g. User)
│   │   └── reference/       # Reference / lookup entities
│   ├── repositories/      # Data access
│   ├── schemas/             # Pydantic request/response models
│   └── services/            # Business logic
├── alembic/                 # Migration scripts
├── docs/                    # HTML docs & PlantUML sources
├── requirements.txt
├── Makefile
├── .env.example             # Copy to `.env` and adjust
└── README.md
```

---

## Prerequisites

- **Python** 3.11 or newer (tested with 3.14)
- **make** (optional but recommended; all common tasks are wrapped in the `Makefile`)

---

## Getting started

1. Clone the repository (or open the project folder).
2. Create and activate a virtual environment

```bash
make venv
source .venv/bin/activate
```

3. Install dependencies

```bash
make install
```

4. Configure environment

```bash
cp .env.example .env
# Edit .env: especially SQLITE_DB_PATH, APP_HOST, APP_PORT
```

5. Apply database migrations

```bash
make migrate
```

6. Start the API

```bash
make run
```

The server reads `APP_HOST` and `APP_PORT` from `.env` (see [Configuration](#configuration)).

---

## Configuration

Variables are loaded from `.env` in the project root (see `app/core/config.py`).

| Variable          | Description                                      | Example              |
| ----------------- | ------------------------------------------------ | -------------------- |
| `APP_NAME`        | Title shown in OpenAPI                           | `Study App API`      |
| `APP_ENV`         | Logical environment label                        | `local`              |
| `APP_HOST`        | Bind address for Uvicorn                         | `127.0.0.1`          |
| `APP_PORT`        | Listen port                                      | `8000`               |
| `SQLITE_DB_PATH`  | SQLite database file (relative or absolute path) | `study_app.db`       |

> **Security:** do not commit `.env` with secrets. The repository includes `.env.example` only. Local `*.db` files are listed in `.gitignore`.

---

## API documentation (Swagger)

After the server is up:

| Resource    | URL |
| ----------- | --- |
| **Swagger UI** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (use your `APP_HOST`/`APP_PORT` if different) |
| **ReDoc**      | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |

Interactive docs include request schemas, response models, and validation rules generated from Pydantic.

---

## HTTP endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET`  | `/health` | Liveness / health check |
| `POST` | `/api/v1/users/register` | Register or update a user (validated body) |

---

## Project documentation (HTML & UML)

- Human-readable requirements and diagrams: open **`docs/index.html`** in a browser.
- PlantUML sources live under `docs/uml/`; rendered PNGs can be regenerated with:

  ```bash
  make docs
  make docs-watch   # regenerate when .puml files change
  ```

---

## Makefile reference

| Command | Purpose |
| ------- | ------- |
| `make help` | Print available targets |
| `make venv` | Create `.venv` if missing |
| `make install` | Install `requirements.txt` into `.venv` |
| `make run` | Run API with Uvicorn (reload), using `.env` |
| `make migrate` | `alembic upgrade head` |
| `make migration name=...` | `alembic revision --autogenerate -m "..."` |
| `make docs` | Regenerate UML PNGs once |
| `make docs-watch` | Watch UML and regenerate |


---

## License

MIT
