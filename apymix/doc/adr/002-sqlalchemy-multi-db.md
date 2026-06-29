# ADR-002 : SQLModel for Multi-DB Abstraction (Unified Models)

**Status:** Accepted (revised)
**Date:** 2026-02-24

## Context

Apymix must work with SQLite in development (simplicity, no server to install) and PostgreSQL in production (robustness, performance, concurrency). The business code must not change between the two environments.

Furthermore, in a solo developer context, the duplication between SQLAlchemy models (ORM) and Pydantic schemas (validation/serialization) is a significant overhead: each field is declared twice, and both must stay in sync manually.

## Considered options

### Option A : SQLAlchemy 2.0 (async) + Pydantic separate

Most mature Python ORM, with async support via `asyncio` and specific drivers (`aiosqlite`, `asyncpg`). Pydantic schemas are declared separately.

- **Pros:** Mature ecosystem, rich documentation, Alembic for migrations, native multi-engine support, modern `Mapped[]` pattern, large community, full control.
- **Cons:** Model/schema duplication (each field declared twice), more boilerplate, manual sync between ORM and schema.

### Option B : Tortoise ORM

Async-first ORM for Python, inspired by the Django ORM.

- **Pros:** Simple API, native async, less boilerplate.
- **Cons:** Smaller ecosystem, fewer supported drivers, less mature migrations (Aerich), smaller community, uncertainty about longevity.

### Option C : SQLModel

Library created by Sebastián Ramírez (tiangolo, creator of FastAPI) combining SQLAlchemy + Pydantic in a single model.

- **Pros:** One model = ORM + validation/serialization schema. Native integration with FastAPI (same author). Built ON SQLAlchemy 2.0 (so Alembic works). Less code to maintain. Gentle learning curve for anyone familiar with Pydantic and FastAPI.
- **Cons:** Still 0.x. Some advanced SQLAlchemy patterns are less accessible. Many-to-many relationships require a bit more configuration.

### Option D : DuckDB

Embedded analytics database.

- **Pros:** Performant for analytics, no server.
- **Cons:** OLAP-oriented, not designed for transactional CRUD, no native SQLAlchemy support, no concurrent multi-connection write mode.

## Decision

**Option C: SQLModel.**

For a solo developer building simple CRUD APIs, the reduction in boilerplate is decisive:

```python
# BEFORE (SQLAlchemy + Pydantic separate): ~30 lines for a model
class RSVPModel(Base):                    # ORM
    __tablename__ = "rsvps"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    fullname: Mapped[str] = mapped_column(String(200))
    # ... repeat each field

class RSVPCreate(BaseModel):              # Pydantic (input)
    fullname: str
    # ... re-declare each field

class RSVPRead(BaseModel):                # Pydantic (output)
    id: uuid.UUID
    fullname: str
    # ... once more

# AFTER (SQLModel): ~15 lines for the same result
class RSVP(TimestampMixin, table=True):   # ORM (table=True)
    __tablename__ = "rsvps"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(max_length=255, unique=True)
    fullname: str = Field(max_length=200)
    attending: bool = False
    guests: list | None = Field(default=None, sa_column=Column(JSON))

class RSVPCreate(SQLModel):               # Input (Pydantic validation)
    email: EmailStr
    fullname: str = Field(min_length=3, max_length=200)
    attending: bool
    guests: list[GuestItem] = []

class RSVPRead(SQLModel):                 # Output
    id: uuid.UUID
    fullname: str
    guest_count: int                      # computed: len(guests) + 1
```

SQLModel is built ON SQLAlchemy 2.0, so:
- Alembic works normally for migrations
- The `aiosqlite` and `asyncpg` drivers are supported
- You can drop down to SQLAlchemy level for advanced cases

DuckDB is ruled out because it is analytics-oriented (OLAP), not transactional (OLTP).

## Consequences

### Positive
- **DRY**: each field is declared only once
- Versioned migrations via Alembic (same as pure SQLAlchemy)
- Pydantic validation integrated into the ORM models
- Same author as FastAPI = natural and consistent integration
- Less code = fewer bugs, simplified maintenance

### Negative
- 0.x version (but widely used in production, active author)
- If the `apymix` module is open-sourced, the dependency on SQLModel (rather than SQLAlchemy alone) can be a blocker for some advanced users
- You must enable `PRAGMA foreign_keys = ON` for SQLite

### Risks
- If SQLModel stagnates, we can migrate to pure SQLAlchemy (models with `table=True` ARE SQLAlchemy models). The lock-in risk is low.
- If PostgreSQL-specific features are used (JSONB, arrays), they won't be available in SQLite. → Mitigation: stick to standard types.
