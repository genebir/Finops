"""GET /api/anomaly-root-cause — Heuristic root-cause analysis for an anomaly event.

Compares the target resource's cost on a given date against:
- The same resource's prior 7-day baseline (spike vs new_resource detection)
- Peer resources in the same service category on the same date (isolated vs systemic)
- The owning team's daily cost trend (team-wide change context)

Returns a single classified root cause (`new_resource`, `cost_spike`, `peer_spike`,
or `unknown`) with a 0–1 confidence score and a short human-readable reason.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..deps import db_read, f

router = APIRouter(tags=["anomalies"])

_PEER_SPIKE_RATIO = 1.5  # avg peer cost vs avg peer baseline before flagging "peer_spike"


def _classify(
    target_cost: float,
    avg_prior_7d: float,
    days_observed: int,
    peers_also_spiked: bool,
    peer_count: int,
) -> tuple[str, float, str]:
    """Pick the best-fit cause + confidence + human-readable reason."""
    # New resource: no recent baseline at all
    if days_observed == 0:
        return (
            "new_resource",
            0.9,
            "No prior 7-day cost history — resource appeared today.",
        )

    spike_ratio = target_cost / avg_prior_7d if avg_prior_7d > 0 else float("inf")

    # Peer-wide event: this resource AND its peers both jumped
    if peers_also_spiked and peer_count > 0 and spike_ratio >= 1.5:
        return (
            "peer_spike",
            0.6,
            f"Cost rose {spike_ratio:.1f}× and {peer_count} peer resource(s) "
            "in the same service also spiked — likely a service-wide event.",
        )

    # Isolated cost spike on this resource
    if spike_ratio >= 3.0:
        return (
            "cost_spike",
            0.8,
            f"Cost is {spike_ratio:.1f}× the 7-day average while peers stayed normal.",
        )
    if spike_ratio >= 2.0:
        return (
            "cost_spike",
            0.6,
            f"Cost is {spike_ratio:.1f}× the 7-day average — moderate spike.",
        )

    return (
        "unknown",
        0.3,
        "Cost is within recent range and peers look normal — no obvious driver.",
    )


@router.get("/api/anomaly-root-cause")
def root_cause(
    resource_id: str = Query(..., min_length=1),
    charge_date: date = Query(..., description="Date of the anomaly event (YYYY-MM-DD)"),
) -> dict[str, Any]:
    seven_days_ago = charge_date - timedelta(days=7)

    with db_read() as conn:
        # 1) Target row on the anomaly date — also serves as 404 guard
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT CAST(SUM(effective_cost) AS DOUBLE PRECISION),
                       MAX(service_name),
                       MAX(service_category),
                       MAX(team),
                       MAX(env),
                       MAX(provider)
                FROM fact_daily_cost
                WHERE resource_id = %s AND charge_date = %s
                """,
                (resource_id, charge_date),
            )
            row = cur.fetchone()

        if not row or row[0] is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No cost record for resource '{resource_id}' on "
                    f"{charge_date.isoformat()}"
                ),
            )

        target_cost = f(row[0])
        service_name = row[1] or "unknown"
        team = row[3] or "unknown"
        env = row[4] or "unknown"
        provider = row[5] or "unknown"

        # 2) Prior 7-day baseline for this resource (excludes the event day)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT CAST(AVG(daily_cost) AS DOUBLE PRECISION),
                       CAST(MAX(daily_cost) AS DOUBLE PRECISION),
                       CAST(MIN(daily_cost) AS DOUBLE PRECISION),
                       COUNT(*)
                FROM (
                    SELECT charge_date,
                           SUM(effective_cost) AS daily_cost
                    FROM fact_daily_cost
                    WHERE resource_id = %s
                      AND charge_date >= %s
                      AND charge_date < %s
                    GROUP BY charge_date
                ) AS daily
                """,
                (resource_id, seven_days_ago, charge_date),
            )
            hist = cur.fetchone()

        avg_prior_7d = f(hist[0]) if hist else 0.0
        max_prior_7d = f(hist[1]) if hist else 0.0
        min_prior_7d = f(hist[2]) if hist else 0.0
        days_observed = int(hist[3]) if hist else 0
        spike_ratio = target_cost / avg_prior_7d if avg_prior_7d > 0 else None

        # 3) Peer comparison — same service_name on the same date, excluding self
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT CAST(AVG(peer_cost) AS DOUBLE PRECISION),
                       CAST(MAX(peer_cost) AS DOUBLE PRECISION),
                       COUNT(*)
                FROM (
                    SELECT resource_id,
                           SUM(effective_cost) AS peer_cost
                    FROM fact_daily_cost
                    WHERE service_name = %s
                      AND charge_date = %s
                      AND resource_id <> %s
                    GROUP BY resource_id
                ) AS peers
                """,
                (service_name, charge_date, resource_id),
            )
            peer_today = cur.fetchone()

        peer_avg_cost = f(peer_today[0]) if peer_today else 0.0
        peer_max_cost = f(peer_today[1]) if peer_today else 0.0
        peer_count = int(peer_today[2]) if peer_today else 0

        # Peer baseline (prior 7-day avg) to see if they spiked too
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT CAST(AVG(daily_cost) AS DOUBLE PRECISION)
                FROM (
                    SELECT charge_date, SUM(effective_cost) AS daily_cost
                    FROM fact_daily_cost
                    WHERE service_name = %s
                      AND resource_id <> %s
                      AND charge_date >= %s
                      AND charge_date < %s
                    GROUP BY charge_date
                ) AS daily
                """,
                (service_name, resource_id, seven_days_ago, charge_date),
            )
            peer_hist = cur.fetchone()

        peer_baseline_daily = f(peer_hist[0]) if peer_hist else 0.0
        # Today's peer-cumulative vs prior 7-day daily-average is the right comparison
        peer_today_total = peer_avg_cost * peer_count
        peers_also_spiked = (
            peer_baseline_daily > 0
            and peer_today_total / peer_baseline_daily >= _PEER_SPIKE_RATIO
        )

        # 4) Team-wide trend: today vs prior 7-day daily average
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT CAST(SUM(effective_cost) AS DOUBLE PRECISION)
                FROM fact_daily_cost
                WHERE team = %s AND charge_date = %s
                """,
                (team, charge_date),
            )
            team_today = cur.fetchone()

        team_total_today = f(team_today[0]) if team_today else 0.0

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT CAST(AVG(daily_total) AS DOUBLE PRECISION)
                FROM (
                    SELECT charge_date, SUM(effective_cost) AS daily_total
                    FROM fact_daily_cost
                    WHERE team = %s
                      AND charge_date >= %s
                      AND charge_date < %s
                    GROUP BY charge_date
                ) AS daily
                """,
                (team, seven_days_ago, charge_date),
            )
            team_hist = cur.fetchone()

        team_avg_prior_7d = f(team_hist[0]) if team_hist else 0.0
        team_change_pct: float | None
        if team_avg_prior_7d > 0:
            team_change_pct = (team_total_today - team_avg_prior_7d) / team_avg_prior_7d * 100
        else:
            team_change_pct = None

    cause, confidence, reason = _classify(
        target_cost=target_cost,
        avg_prior_7d=avg_prior_7d,
        days_observed=days_observed,
        peers_also_spiked=peers_also_spiked,
        peer_count=peer_count,
    )

    return {
        "resource_id": resource_id,
        "charge_date": charge_date.isoformat(),
        "service_name": service_name,
        "team": team,
        "env": env,
        "provider": provider,
        "target_cost": round(target_cost, 2),
        "history": {
            "avg_prior_7d": round(avg_prior_7d, 2),
            "max_prior_7d": round(max_prior_7d, 2),
            "min_prior_7d": round(min_prior_7d, 2),
            "days_observed": days_observed,
            "spike_ratio": round(spike_ratio, 2) if spike_ratio is not None else None,
        },
        "peers": {
            "service_name": service_name,
            "peer_count": peer_count,
            "peer_avg_cost": round(peer_avg_cost, 2),
            "peer_max_cost": round(peer_max_cost, 2),
            "peer_baseline_daily": round(peer_baseline_daily, 2),
            "peers_also_spiked": peers_also_spiked,
        },
        "team_context": {
            "team": team,
            "team_total_today": round(team_total_today, 2),
            "team_avg_prior_7d": round(team_avg_prior_7d, 2),
            "team_change_pct": round(team_change_pct, 1) if team_change_pct is not None else None,
        },
        "root_cause": {
            "cause": cause,
            "confidence": confidence,
            "reason": reason,
        },
    }
