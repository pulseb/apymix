"""Script de seed — crée le premier utilisateur admin en BDD.

Usage :
    python -m scripts.seed_admin
    python -m scripts.seed_admin --email admin@papi.local --password secret123
"""

import argparse
import asyncio

from sqlmodel import select

# Import dynamique de tous les modèles (papi + APIs) pour SQLModel.metadata
from apymix.auth.models import User, UserAccount
from apymix.auth.security import get_password_hash
from apymix.db.session import get_db, init_db
from apymix.discovery import import_all_api_models


async def seed_admin(email: str, password: str) -> None:
    """Crée un utilisateur admin s'il n'existe pas déjà."""
    import_all_api_models()
    await init_db()

    async for db in get_db():
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⚠️  L'utilisateur '{email}' existe déjà (id={existing.id})")
            return

        user = User(
            email=email,
            roles=["admin", "user"],
            status="active",
        )
        db.add(user)
        await db.flush()  # obtenir user.id

        account = UserAccount(
            user_id=user.id,
            provider="password",
            provider_user_id=email,
            password_hash=get_password_hash(password),
        )
        db.add(account)
        await db.commit()
        await db.refresh(user)

        print(f"✅ Admin créé : {email} (id={user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Créer un utilisateur admin")
    parser.add_argument("--email", default="admin@papi.local", help="Email de l'admin")
    parser.add_argument("--password", default="admin", help="Mot de passe de l'admin")
    args = parser.parse_args()

    asyncio.run(seed_admin(args.email, args.password))


if __name__ == "__main__":
    main()
