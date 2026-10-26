import asyncio
import os
import uuid
from sys import argv
from database import engine, Base, User
from sqlalchemy.ext.asyncio import async_sessionmaker
from passlib.context import CryptContext

# Re-use the exact same password hashing context from security.py
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def seed_initial_admin(username: str, plain_password: str):
    """
    Connects to Percona PostgreSQL, ensures tables are initialized,
    and inserts an encrypted initial administrator account.
    """
    print(f"[System] Connecting to database to seed user: '{username}'...")
    
    # 1. Establish an async session bound to the Percona engine context
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        async with session.begin():
            # 2. Ensure your schemas exist (safeguard for brand new environments)
            await session.run_sync(Base.metadata.create_all)
            
            # 3. Securely calculate the bcrypt hash string of the plain password
            hashed_pass = pwd_context.hash(plain_password)
            
            # 4. Construct the structural database record mapping the 'admin' role
            admin_user = User(
                id=str(uuid.uuid4()),
                username=username,
                hashed_password=hashed_pass,
                is_active=True,
                role="admin"
            )
            
            session.add(admin_user)
            
        # Commit the transaction block atomically to the database disk
        await session.commit()
        
    print(f"Successfully committed administration account token to disk.")
    print(f"Username: {username}")
    print(f"Role Tier: admin")

if __name__ == "__main__":
    # Allow passing custom variables via command arguments or fall back to defaults
    user_arg = argv[1] if len(argv) > 1 else "admin_user"
    pass_arg = argv[2] if len(argv) > 2 else "VaultSecuredPassword123!"
    
    # Ensure database connection url environment variable is verified or set
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://nornir_admin:Pass123!@127.0.0.1:5432/nornir_db"
        
    asyncio.run(seed_initial_admin(user_arg, pass_arg))

