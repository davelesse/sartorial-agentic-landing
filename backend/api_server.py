"""
Sartorial Agentic — Standalone server entry point.
Run with: python api_server.py
"""

import os
import uvicorn

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
APP_ENV = os.getenv("APP_ENV", "development")

if __name__ == "__main__":
    is_dev = APP_ENV == "development"

    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=is_dev,
        workers=1 if is_dev else 4,
        loop="uvloop",
        http="httptools",
        log_level="debug" if is_dev else "info",
    )
