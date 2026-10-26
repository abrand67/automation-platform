import os
from datetime import datetime
from sqlalchemy import String, JSON, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy.orm import relationship

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://nornir_admin:Pass123!@127.0.0.1:5432/nornir_db")

engine = create_async_engine(DATABASE_URL, pool_size=20, max_overflow=10)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Many-to-Many Bridge Table linking User Groups to explicit granular Access Permissions
group_permission_association = Table(
    'group_permission_association', Base.metadata,
    Column('group_id', String, ForeignKey('groups.id', ondelete='CASCADE')),
    Column('permission_id', String, ForeignKey('permissions.id', ondelete='CASCADE'))

class Base(DeclarativeBase):
    pass

class JobExecution(Base):
    __tablename__ = "job_executions"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    filters: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String, default="viewer") # admin, operator, viewer

class Group(Base):
    __tablename__ = "groups"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    permissions = relationship("Permission", secondary=group_permission_association)

class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    object_type: Mapped[str] = mapped_column(String, nullable=False) # e.g., "project", "inventory", "credential"
    object_id: Mapped[str] = mapped_column(String, nullable=False)   # Target record primary key UUID, or "*" for global
    action: Mapped[str] = mapped_column(String, nullable=False)      # e.g., "read", "execute", "write"

async def get_db_session():
    async with async_session() as session:
        yield session

