"""Point d'entrée CLI : `uv run apymix` lance uvicorn avec la config depuis l'environnement."""

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Lance le serveur Apymix")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="Adresse d'écoute")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Port d'écoute")
    parser.add_argument("--reload", action="store_true", default=os.getenv("ENV", "production") == "development", help="Hot reload (dev)")
    parser.add_argument("--workers", type=int, default=int(os.getenv("WORKERS", "1")), help="Nombre de workers (incompatible avec --reload)")
    parser.add_argument("--seed", action="store_true", help="Réinitialise la BDD et rejoue le seed")
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
