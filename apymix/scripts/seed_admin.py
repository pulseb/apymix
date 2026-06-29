"""Seed script — creates the first admin user in the database.

Usage:
    python -m scripts.seed_admin
    python -m scripts.seed_admin --email admin@apymix.local --password secret123
"""

import argparse
import asyncio

from sqlmodel import select

# Dynamic import of all models (apymix + APIs) for SQLModel.metadata
from apymix.auth.models import User, UserAccount
from apymix.auth.security import get_password_hash
from apymix.db.session import get_db, init_db
from apymix.discovery import import_all_api_models


async def seed_admin(email: str, password: str) -> None:
    """Create an admin user if it does not already exist."""
    import_all_api_models()
    await init_db()

    async for db in get_db():
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⚠️  User '{email}' already exists (id={existing.id})")
            return

        user = User(
            email=email,
            roles=["admin", "user"],
            status="active",
        )
        db.add(user)
        await db.flush()  # obtain user.id

        account = UserAccount(
            user_id=user.id,
            provider="password",
            provider_user_id=email,
            password_hash=get_password_hash(password),
        )
        db.add(account)
        await db.commit()
        await db.refresh(user)

        print(f"✅ Admin created: {email} (id={user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--email", default="admin@apymix.local", help="Admin email")
    parser.add_argument("--password", default="admin", help="Admin password")
    args = parser.parse_args()

    asyncio.run(seed_admin(args.email, args.password))


if __name__ == "__main__":
    main()
