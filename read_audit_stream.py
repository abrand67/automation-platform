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
import sys
import json
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database import Base, ActivityStream

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("CRITICAL ERROR: DATABASE_URL is unassigned inside your .env file.", file=sys.stderr)
    sys.exit(1)

async def fetch_and_display_audit_logs(limit_records: int = 50, filter_action: str = None):
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    print("=" * 115)
    print(f"{'TIMESTAMP (UTC)':<22} | {'ACTOR':<15} | {'ACTION':<10} | {'OBJECT TYPE':<15} | {'OBJECT ID':<36}")
    print("=" * 115)
    async with async_session() as session:
        query = select(ActivityStream).order_by(desc(ActivityStream.timestamp))
        if filter_action: query = query.filter(ActivityStream.action == filter_action.upper())
        result = await session.execute(query.limit(limit_records))
        records = result.scalars().all()
        for row in records:
            print(f"{row.timestamp.strftime('%Y-%m-%d %H:%M:%S'):<22} | {row.actor_username:<15} | {row.action:<10} | {row.object_type:<15} | {row.object_id:<36}")
            if row.changes_json:
                print("   👉 Context / Modifications Applied:")
                for line in json.dumps(row.changes_json, indent=6).splitlines(): print(f"      {line}")
                print("-" * 115)
    await engine.dispose()

if __name__ == "__main__":
    lim = int(sys.argv) if len(sys.argv) > 1 else 50
    filt = sys.argv if len(sys.argv) > 2 else None
    asyncio.run(fetch_and_display_audit_logs(lim, filt))
