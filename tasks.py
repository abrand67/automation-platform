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

import uuid
from datetime import datetime
from sqlalchemy import String, JSON, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, async_session

class JobHistorySummary(Base):
    __tablename__ = "job_history_summaries"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    summary_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    raw_console_output: Mapped[str] = mapped_column(Text, nullable=False)

async def archive_job_run(job_id: str, nornir_results, raw_logs_list: list):
    summary = {"total_hosts": len(nornir_results), "failed_hosts": [], "passed_hosts": []}
    success_flag = True
    for host, host_result in nornir_results.items():
        if host_result.failed:
            success_flag = False
            summary["failed_hosts"].append({"host": host, "exception": str(host_result.exception)})
        else:
            summary["passed_hosts"].append({"host": host, "changed": getattr(host_result, "changed", False)})

    historical_record = JobHistorySummary(
        id=str(uuid.uuid4()), job_id=job_id, success=success_flag, summary_data=summary, raw_console_output="\n".join(raw_logs_list)
    )
    async with async_session() as session:
        async with session.begin(): session.add(historical_record)
        await session.commit()
