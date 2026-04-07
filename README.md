# Study App API

Backend service on FastAPI + SQLAlchemy + Alembic + SQLite.

## Requirements

- Python 3.11+ (you use 3.14 locally)
- `make`

## Quick Start

1. Create virtual environment:

```bash
make venv
```

2. Activate it:

```bash
source .venv/bin/activate
```

3. Install dependencies:

```bash
make install
```

4. Apply migrations:

```bash
make migrate
```

5. Run API:

```bash
make run
```

## How to Open Swagger

After `make run`, open:

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## Current Implemented Endpoint

- `POST /api/v1/users/register`

## Useful Commands

- Create migration:

```bash
make migration name=add_new_attrs
```

- Apply all pending migrations:

```bash
make migrate
```

- Regenerate UML docs once:

```bash
make docs
```

- Watch UML docs and regenerate automatically:

```bash
make docs-watch
```

## Environment Variables

Configured in `.env`:

- `APP_NAME`
- `APP_ENV`
- `APP_HOST`
- `APP_PORT`
- `SQLITE_DB_PATH`
