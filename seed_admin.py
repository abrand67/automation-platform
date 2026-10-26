# Copyright 2026 Allan Brand
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://apache.org
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific permissions and
# limitations under the License.

import asyncio
import os
import uuid
from sys import argv
from dotenv import load_dotenv

load_dotenv()

from database import engine, Base, User
from sqlalchemy.ext.asyncio import async_sessionmaker
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def seed_initial_admin(username: str, plain_password: str):
    print(f"[System] Directing session to initialize admin table row user: '{username}'...")
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        async with session.begin():
            await session.run_sync(Base.metadata.create_all)
            hashed_pass = pwd_context.hash(plain_password)
            admin_user = User(id=str(uuid.uuid4()), username=username, hashed_password=hashed_pass, is_active=True, role="admin")
            session.add(admin_user)
        await session.commit()
    print("[System] Transaction finalized. Admin profile generated.")

if __name__ == "__main__":
    user_arg = argv if len(argv) > 1 else "admin_user"
    pass_arg = argv if len(argv) > 2 else "VaultSecuredPassword123!"
    asyncio.run(seed_initial_admin(user_arg, pass_arg))
