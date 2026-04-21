"""FinOps Platform — Streamlit 웹 대시보드.

실행:
    uv run streamlit run scripts/streamlit_app.py

환경변수:
    DUCKDB_PATH: DuckDB 파일 경로 (기본: data/marts.duckdb)
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "data/marts.duckdb")

st.set_page_config(
    page_title="FinOps Platform",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=300)
def _query(sql: str) -> list[dict[str, object]]:
    """DuckDB 쿼리 결과를 dict 리스트로 반환한다. 파일 없으면 빈 리스트."""
    if not Path(_DUCKDB_PATH).exists():
        return []
    try:
        conn = duckdb.connect(_DUCKDB_PATH, read_only=True)
        result = conn.execute(sql).fetchdf()
        conn.close()
        return result.to_dict("records")  # type: ignore[return-value]
    except Exception:
        return []


@st.cache_data(ttl=300)
def _available_months() -> list[str]:
    rows = _query(
        "SELECT DISTINCT STRFTIME(charge_date, '%Y-%m') AS m "
        "FROM fact_daily_cost ORDER BY m DESC LIMIT 24"
    )
    return [str(r["m"]) for r in rows]


@st.cache_data(ttl=300)
def _available_providers() -> list[str]:
    rows = _query("SELECT DISTINCT provider FROM fact_daily_cost ORDER BY provider")
    return ["all"] + [str(r["provider"]) for r in rows]


def _provider_filter(selected: str) -> str:
    if selected == "all":
        return ""
    return f"AND provider = '{selected}'"


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("FinOps Platform")
st.sidebar.markdown("---")

months = _available_months()
if months:
    selected_month = st.sidebar.selectbox("Billing Month", months, index=0)
else:
    selected_month = ""
    st.sidebar.info("No data yet. Run Dagster assets first.")

providers = _available_providers()
selected_provider = st.sidebar.selectbox("Cloud Provider", providers, index=0)

st.sidebar.markdown("---")
st.sidebar.caption(f"Data source: `{_DUCKDB_PATH}`")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_overview, tab_explorer, tab_anomaly, tab_forecast, tab_budget, tab_chargeback = st.tabs([
    "📊 Overview",
    "🔍 Cost Explorer",
    "🚨 Anomalies",
    "📈 Forecast",
    "💳 Budget",
    "📑 Chargeback",
])

# ── Tab 1: Overview ───────────────────────────────────────────────────────────

with tab_overview:
    st.header("Overview")
    if not selected_month:
        st.info("No data available.")
    else:
        pf = _provider_filter(selected_provider)

        total_rows = _query(f"""
            SELECT
                COUNT(DISTINCT resource_id) AS resources,
                SUM(CAST(effective_cost AS DOUBLE)) AS total_cost,
                COUNT(DISTINCT provider) AS providers,
                COUNT(DISTINCT cost_unit_key) AS cost_units
            FROM fact_daily_cost
            WHERE STRFTIME(charge_date, '%Y-%m') = '{selected_month}'
            {pf}
        """)
        if total_rows:
            r = total_rows[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Cost (MTD)", f"${float(r.get('total_cost') or 0):,.2f}")
            c2.metric("Resources", int(r.get("resources") or 0))
            c3.metric("Providers", int(r.get("providers") or 0))
            c4.metric("Cost Units", int(r.get("cost_units") or 0))

        st.subheader("Daily Cost Trend")
        daily = _query(f"""
            SELECT
                charge_date,
                provider,
                SUM(CAST(effective_cost AS DOUBLE)) AS cost
            FROM fact_daily_cost
            WHERE STRFTIME(charge_date, '%Y-%m') = '{selected_month}'
            {pf}
            GROUP BY charge_date, provider
            ORDER BY charge_date
        """)
        if daily:
            import pandas as pd
            df = pd.DataFrame(daily)
            fig = px.area(
                df, x="charge_date", y="cost", color="provider",
                title="Daily Cost by Provider",
                labels={"charge_date": "Date", "cost": "Cost (USD)"},
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Cost by Service")
        by_service = _query(f"""
            SELECT
                service_name,
                SUM(CAST(effective_cost AS DOUBLE)) AS cost
            FROM fact_daily_cost
            WHERE STRFTIME(charge_date, '%Y-%m') = '{selected_month}'
            {pf}
            GROUP BY service_name
            ORDER BY cost DESC
            LIMIT 15
        """)
        if by_service:
            import pandas as pd
            df_svc = pd.DataFrame(by_service)
            fig2 = px.bar(
                df_svc, x="cost", y="service_name", orientation="h",
                title="Top 15 Services by Cost",
                labels={"cost": "Cost (USD)", "service_name": "Service"},
            )
            fig2.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig2, use_container_width=True)

# ── Tab 2: Cost Explorer ──────────────────────────────────────────────────────

with tab_explorer:
    st.header("Cost Explorer")
    if not selected_month:
        st.info("No data available.")
    else:
        pf = _provider_filter(selected_provider)

        group_by = st.selectbox(
            "Group By",
            ["team", "product", "env", "cost_unit_key", "resource_id", "service_name"],
            index=0,
        )
        top_n = st.slider("Top N", 5, 50, 20)

        rows = _query(f"""
            SELECT
                {group_by} AS dimension,
                SUM(CAST(effective_cost AS DOUBLE)) AS cost,
                COUNT(DISTINCT resource_id) AS resources
            FROM fact_daily_cost
            WHERE STRFTIME(charge_date, '%Y-%m') = '{selected_month}'
            {pf}
            GROUP BY {group_by}
            ORDER BY cost DESC
            LIMIT {top_n}
        """)
        if rows:
            import pandas as pd
            df = pd.DataFrame(rows)
            col1, col2 = st.columns([2, 1])
            with col1:
                fig = px.bar(
                    df, x="cost", y="dimension", orientation="h",
                    title=f"Top {top_n} by {group_by}",
                    labels={"cost": "Cost (USD)", "dimension": group_by},
                )
                fig.update_layout(yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig_pie = px.pie(df, names="dimension", values="cost", title="Cost Share")
                st.plotly_chart(fig_pie, use_container_width=True)

            st.dataframe(df, use_container_width=True)

# ── Tab 3: Anomalies ──────────────────────────────────────────────────────────

with tab_anomaly:
    st.header("Anomaly Detection")
    if not selected_month:
        st.info("No data available.")
    else:
        anomaly_rows = _query(f"""
            SELECT
                resource_id, cost_unit_key, team, product, env,
                charge_date,
                CAST(effective_cost AS DOUBLE) AS effective_cost,
                CAST(mean_cost AS DOUBLE) AS mean_cost,
                z_score, severity, detector_name
            FROM anomaly_scores
            WHERE STRFTIME(charge_date, '%Y-%m') = '{selected_month}'
            ORDER BY ABS(z_score) DESC
            LIMIT 200
        """)
        if anomaly_rows:
            import pandas as pd
            df = pd.DataFrame(anomaly_rows)

            sev_counts = df["severity"].value_counts()
            c1, c2, c3 = st.columns(3)
            c1.metric("Critical", int(sev_counts.get("critical", 0)))
            c2.metric("Warning", int(sev_counts.get("warning", 0)))
            c3.metric("OK", int(sev_counts.get("ok", 0)))

            severity_filter = st.multiselect(
                "Filter by Severity",
                ["critical", "warning", "ok"],
                default=["critical", "warning"],
            )
            filtered = df[df["severity"].isin(severity_filter)]

            fig = px.scatter(
                filtered, x="charge_date", y="effective_cost",
                color="severity", size="z_score",
                hover_data=["resource_id", "team", "product", "detector_name"],
                title="Anomalies (size = |z_score|)",
                color_discrete_map={"critical": "red", "warning": "orange", "ok": "green"},
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(filtered, use_container_width=True)
        else:
            st.info("No anomaly data for selected period.")

# ── Tab 4: Forecast ───────────────────────────────────────────────────────────

with tab_forecast:
    st.header("Prophet Forecast")

    forecast_rows = _query("""
        SELECT
            resource_id,
            CAST(predicted_monthly_cost AS DOUBLE) AS predicted,
            CAST(lower_bound_monthly_cost AS DOUBLE) AS lower_bound,
            CAST(upper_bound_monthly_cost AS DOUBLE) AS upper_bound,
            CAST(hourly_cost AS DOUBLE) AS hourly_cost,
            model_trained_at
        FROM dim_prophet_forecast
        ORDER BY predicted DESC
        LIMIT 50
    """)
    if forecast_rows:
        import pandas as pd
        df = pd.DataFrame(forecast_rows)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df["resource_id"], y=df["predicted"],
            name="Predicted",
            error_y={"type": "data", "array": df["upper_bound"] - df["predicted"],
                     "arrayminus": df["predicted"] - df["lower_bound"], "visible": True},
        ))
        fig.update_layout(
            title="Prophet Forecast (Top 50 Resources)",
            xaxis_title="Resource ID",
            yaxis_title="Monthly Cost (USD)",
            xaxis={"tickangle": -45},
        )
        st.plotly_chart(fig, use_container_width=True)

        variance_rows = _query(f"""
            SELECT resource_id, status, billing_month,
                   CAST(forecast_monthly_cost AS DOUBLE) AS forecast,
                   CAST(actual_monthly_cost AS DOUBLE) AS actual,
                   variance_pct
            FROM dim_forecast_variance_prophet
            ORDER BY ABS(variance_pct) DESC NULLS LAST
            LIMIT 50
        """ if not selected_month else f"""
            SELECT resource_id, status, billing_month,
                   CAST(forecast_monthly_cost AS DOUBLE) AS forecast,
                   CAST(actual_monthly_cost AS DOUBLE) AS actual,
                   variance_pct
            FROM dim_forecast_variance_prophet
            WHERE billing_month = '{selected_month}'
            ORDER BY ABS(variance_pct) DESC NULLS LAST
            LIMIT 50
        """)
        if variance_rows:
            st.subheader("Forecast vs Actual Variance")
            df_var = pd.DataFrame(variance_rows)
            fig2 = px.scatter(
                df_var, x="forecast", y="actual", color="status",
                hover_data=["resource_id", "variance_pct"],
                title="Prophet Forecast vs Actual",
                labels={"forecast": "Forecast (USD)", "actual": "Actual (USD)"},
                color_discrete_map={
                    "within_bounds": "green",
                    "above_upper": "red",
                    "below_lower": "blue",
                    "no_actual": "gray",
                },
            )
            fig2.add_shape(
                type="line", x0=0, y0=0, x1=df_var["forecast"].max(), y1=df_var["forecast"].max(),
                line={"color": "gray", "dash": "dot"},
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(df_var, use_container_width=True)
    else:
        st.info("No forecast data. Run prophet_forecast asset first.")

# ── Tab 5: Budget ─────────────────────────────────────────────────────────────

with tab_budget:
    st.header("Budget Management")

    budget_status = _query(f"""
        SELECT team, env, budget_amount, actual_cost, utilization_pct, status
        FROM dim_budget_status
        WHERE billing_month = '{selected_month}'
        ORDER BY utilization_pct DESC
    """ if selected_month else "SELECT 1 WHERE FALSE")

    if budget_status:
        import pandas as pd
        df = pd.DataFrame(budget_status)

        over_count = len(df[df["status"] == "over"])
        warn_count = len(df[df["status"] == "warning"])
        ok_count = len(df[df["status"] == "ok"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Over Budget", over_count, delta_color="inverse")
        c2.metric("Warning", warn_count, delta_color="off")
        c3.metric("OK", ok_count)

        fig = px.bar(
            df, x="utilization_pct", y=df["team"] + "/" + df["env"],
            orientation="h", color="status",
            title="Budget Utilization by Team/Env",
            labels={"utilization_pct": "Utilization (%)", "y": "Team/Env"},
            color_discrete_map={"over": "red", "warning": "orange", "ok": "green"},
        )
        fig.add_vline(x=100, line_color="red", line_dash="dash", annotation_text="100%")
        fig.add_vline(x=80, line_color="orange", line_dash="dash", annotation_text="80%")
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No budget status data. Run budget_alerts asset first.")

    st.subheader("Budget Configuration")
    budget_config = _query(
        "SELECT team, env, budget_amount, billing_month, updated_at "
        "FROM dim_budget ORDER BY team, env"
    )
    if budget_config:
        import pandas as pd
        st.dataframe(pd.DataFrame(budget_config), use_container_width=True)
    else:
        st.info("No budget configuration found.")

# ── Tab 6: Chargeback ─────────────────────────────────────────────────────────

with tab_chargeback:
    st.header("Chargeback Report")
    if not selected_month:
        st.info("No data available.")
    else:
        cb_rows = _query(f"""
            SELECT provider, team, product, env, cost_unit_key,
                   CAST(actual_cost AS DOUBLE) AS actual_cost,
                   budget_amount, utilization_pct, resource_count
            FROM dim_chargeback
            WHERE billing_month = '{selected_month}'
            ORDER BY actual_cost DESC
        """)
        if cb_rows:
            import pandas as pd
            df = pd.DataFrame(cb_rows)

            total = df["actual_cost"].sum()
            st.metric("Total Chargeback", f"${total:,.2f}")

            col1, col2 = st.columns(2)
            with col1:
                team_total = df.groupby("team")["actual_cost"].sum().reset_index()
                fig = px.pie(team_total, names="team", values="actual_cost", title="Cost by Team")
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                prov_total = df.groupby("provider")["actual_cost"].sum().reset_index()
                fig2 = px.pie(
                    prov_total, names="provider", values="actual_cost", title="Cost by Provider"
                )
                st.plotly_chart(fig2, use_container_width=True)

            st.subheader("Detailed Breakdown")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No chargeback data. Run chargeback asset first.")
