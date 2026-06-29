"""User model — identity and authentication shared across all APIs."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, Relationship, SQLModel

from apymix.db.models import TimestampMixin


class UserBase(SQLModel):
    """Common identity fields (no sa_column — used by Pydantic schemas)."""

    email: str = Field(max_length=255, unique=True, index=True)
    display_name: Optional[str] = Field(default=None, max_length=100)
    roles: List[str] = Field(default_factory=lambda: ["user"])
    status: str = Field(default="active", max_length=20)  # active | suspended | deleted
    is_email_verified: bool = Field(default=False)
    last_login_at: Optional[datetime] = Field(default=None)
    profile: dict = Field(default_factory=dict)


class User(UserBase, TimestampMixin, table=True):
    """User identities table."""

    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # Override JSON fields for DB storage
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
    """Authentication method linked to a user.

    A user can have several accounts: password, api_token, google, etc.
    """

    __tablename__ = "user_accounts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    provider: str = Field(max_length=50, index=True)  # "password" | "api_token" | "google" | …
    # For "password": email. For "api_token": the token. For OAuth: provider uid.
    provider_user_id: Optional[str] = Field(default=None, max_length=255, index=True)
    password_hash: Optional[str] = Field(default=None, max_length=255)  # only for provider="password"
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))  # provider-specific data

    user: Optional[User] = Relationship(back_populates="accounts")


class UserCreate(SQLModel):
    """Schema for creating a user."""

    email: str
    password: str
    display_name: Optional[str] = None
    roles: List[str] = Field(default_factory=lambda: ["user"])


class UserRead(UserBase):
    """Read schema for a user (no sensitive data)."""

    id: uuid.UUID
    api_token: Optional[str] = None  # populated if the user has an active api_token account


class TokenResponse(SQLModel):
    """Authentication response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefreshRequest(SQLModel):
    """Refresh request schema."""

    refresh_token: str


class LoginRequest(SQLModel):
    """Login request schema."""

    email: str
    password: str


class RegisterRequest(SQLModel):
    """Public registration request schema."""

    email: str = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=100)
