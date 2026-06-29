"""CLI entry point: `uv run apymix` launches uvicorn with config from environment variables."""

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the Apymix server")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="Bind address")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Bind port")
    parser.add_argument("--reload", action="store_true", default=os.getenv("ENV", "production") == "development", help="Hot reload (dev)")
    parser.add_argument("--workers", type=int, default=int(os.getenv("WORKERS", "1")), help="Number of workers (incompatible with --reload)")
    parser.add_argument("--seed", action="store_true", help="Reset the database and replay the seed")
    args = parser.parse_args()

    if args.seed:
        os.environ["FORCE_SEED"] = "true"

    uvicorn_kwargs: dict = {
        "app": "apymix.app:app",
        "host": args.host,
        "port": args.port,
        "log_level": os.getenv("LOG_LEVEL", "info").lower(),
    }

    if args.reload:
        uvicorn_kwargs["reload"] = True
    elif args.workers > 1:
        uvicorn_kwargs["workers"] = args.workers

    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    main()
