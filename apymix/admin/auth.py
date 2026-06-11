"""Authentification SQLAdmin — backend session-based."""

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlmodel import select

from apymix.auth.models import User, UserAccount
from apymix.auth.security import verify_password


class AdminAuth(AuthenticationBackend):
    """Backend d'authentification pour SQLAdmin.

    Utilise une session cookie (via itsdangerous) + vérification
    email/password contre la table users.
    """

    def __init__(self, secret_key: str, engine: AsyncEngine) -> None:
        super().__init__(secret_key=secret_key)
        self._engine = engine

    async def login(self, request: Request) -> bool:
        """Vérifie les credentials et crée la session."""
        form = await request.form()
        email = form.get("username", "")
        password = form.get("password", "")

        async with AsyncSession(self._engine, expire_on_commit=False) as session:
            stmt = select(UserAccount).where(
                UserAccount.provider == "password",
                UserAccount.provider_user_id == str(email),
            )
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()
            user = await session.get(User, account.user_id) if account else None

        if user and user.status == "active" and account and verify_password(str(password), account.password_hash or ""):
            request.session.update({"user_id": str(user.id), "user_email": user.email})
            return True

        return False

    async def logout(self, request: Request) -> bool:
        """Supprime la session."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Vérifie si l'utilisateur est connecté (appelé à chaque requête admin)."""
        return "user_id" in request.session
