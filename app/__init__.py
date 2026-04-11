"""Study App service package.

This package contains the main FastAPI application instance, configuration,
and all domain modules responsible for study management functionalities.
It provides endpoints for core Study App features, registers routers,
and integrates business logic, data persistence, and validation layers required
to serve API and UI requests. Support modules for authentication,
middleware, lifecycle events, and service wiring are also located here.

Typical entrypoint: `app/main.py` launches the ASGI app for deployment via
Uvicorn, Gunicorn, or similar servers. Domain modules implement study
tracking, user management, scheduling, and other core capabilities of the service.
"""
