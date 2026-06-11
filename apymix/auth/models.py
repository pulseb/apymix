"""Modèle User — identité et authentification partagées entre toutes les APIs."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, Relationship, SQLModel

from apymix.db.models import TimestampMixin


class UserBase(SQLModel):
    """Champs d'identité communs (sans sa_column — utilisé par les schémas Pydantic)."""

    email: str = Field(max_length=255, unique=True, index=True)
    display_name: Optional[str] = Field(default=None, max_length=100)
    roles: List[str] = Field(default_factory=lambda: ["user"])
    status: str = Field(default="active", max_length=20)  # active | suspended | deleted
    is_email_verified: bool = Field(default=False)
    last_login_at: Optional[datetime] = Field(default=None)
    profile: dict = Field(default_factory=dict)


class User(UserBase, TimestampMixin, table=True):
    """Table des identités utilisateurs."""

    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # Override JSON fields pour le stockage DB
    roles: List[str] = Field(default_factory=lambda: ["user"], sa_column=Column(JSON))
    profile: dict = Field(default_factory=dict, sa_column=Column(JSON))

    accounts: list["UserAccount"] = Relationship(back_populates="user")

    def has_role(self, role: str) -> bool:
        return role in (self.roles or [])

    def add_role(self, role: str) -> None:
        if role not in (self.roles or []):
            self.roles = [*(self.roles or []), role]

    def remove_role(self, role: str) -> None:
        self.roles = [r for r in (self.roles or []) if r != role]


class UserAccount(TimestampMixin, table=True):
    """Méthode d'authentification liée à un utilisateur.

    Un utilisateur peut avoir plusieurs comptes : password, api_token, google…
    """

    __tablename__ = "user_accounts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    provider: str = Field(max_length=50, index=True)  # "password" | "api_token" | "google" | …
    # Pour "password" : email. Pour "api_token" : le token. Pour OAuth : uid fournisseur.
    provider_user_id: Optional[str] = Field(default=None, max_length=255, index=True)
    password_hash: Optional[str] = Field(default=None, max_length=255)  # uniquement provider="password"
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))  # données spécifiques au provider

    user: Optional[User] = Relationship(back_populates="accounts")


class UserCreate(SQLModel):
    """Schéma de création d'un utilisateur."""

    email: str
    password: str
    display_name: Optional[str] = None
    roles: List[str] = Field(default_factory=lambda: ["user"])


class UserRead(UserBase):
    """Schéma de lecture d'un utilisateur (sans données sensibles)."""

    id: uuid.UUID
    api_token: Optional[str] = None  # renseigné si l'utilisateur a un compte api_token actif


class TokenResponse(SQLModel):
    """Schéma de réponse d'authentification."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefreshRequest(SQLModel):
    """Schéma de requête de refresh."""

    refresh_token: str


class LoginRequest(SQLModel):
    """Schéma de requête de login."""

    email: str
    password: str
