"""Monthly pipeline schedule — triggers burn_rate and data_quality on the 2nd of each month."""
from __future__ import annotations

from dagster import DefaultScheduleStatus, RunRequest, ScheduleDefinition, define_asset_job

burn_rate_job = define_asset_job(
    name="burn_rate_job",
    selection=["burn_rate"],
)

data_quality_job = define_asset_job(
    name="data_quality_job",
    selection=["data_quality"],
)

monthly_burn_rate_schedule = ScheduleDefinition(
    name="monthly_burn_rate_schedule",
    cron_schedule="0 6 2 * *",
    job=burn_rate_job,
    default_status=DefaultScheduleStatus.STOPPED,
    description="Runs burn_rate asset at 06:00 UTC on the 2nd of each month.",
)

daily_data_quality_schedule = ScheduleDefinition(
    name="daily_data_quality_schedule",
    cron_schedule="0 7 * * *",
    job=data_quality_job,
    default_status=DefaultScheduleStatus.STOPPED,
    description="Runs data_quality asset daily at 07:00 UTC.",
)
