"""FinOps Platform — Streamlit 웹 대시보드.

실행:
    uv run streamlit run scripts/streamlit_app.py

환경변수:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DBNAME, POSTGRES_USER, POSTGRES_PASSWORD
"""

from __future__ import annotations

import os

import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import psycopg2
import streamlit as st

_PG_DSN = (
    f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
    f"port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.getenv('POSTGRES_DBNAME', 'finops')} "
    f"user={os.getenv('POSTGRES_USER', 'finops_app')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'finops_secret_2026')}"
)

st.set_page_config(
    page_title="FinOps Platform",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design System ──────────────────────────────────────────────────────────────

_FINOPS_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(family="Inter, sans-serif", size=13, color="#1A1714"),
        paper_bgcolor="#FAF7F2",
        plot_bgcolor="#FAF7F2",
        colorway=[
            "#7FB77E", "#6B8CAE", "#D97757", "#8B7FB8",
            "#E8A04A", "#C8553D", "#A89F94", "#5C8A7A",
        ],
        xaxis=dict(
            gridcolor="#E8E2D9", linecolor="#D4CCC0", zeroline=False,
            tickfont=dict(family="JetBrains Mono, monospace", size=11, color="#6B6560"),
        ),
        yaxis=dict(
            gridcolor="#E8E2D9", linecolor="#D4CCC0", zeroline=False,
            tickfont=dict(family="JetBrains Mono, monospace", size=11, color="#6B6560"),
        ),
        legend=dict(
            font=dict(family="Inter, sans-serif", size=12, color="#6B6560"),
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
        ),
        margin=dict(l=48, r=24, t=32, b=48),
        hoverlabel=dict(
            bgcolor="#1A1714", bordercolor="#1A1714",
            font=dict(family="Inter, sans-serif", size=12, color="#FAF7F2"),
        ),
    )
)
pio.templates["finops"] = _FINOPS_TEMPLATE
pio.templates.default = "finops"


def _inject_design_system() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --bg-warm: #FAF7F2;
        --bg-warm-subtle: #F2EDE4;
        --bg-dark: #1A1714;
        --text-primary: #1A1714;
        --text-secondary: #6B6560;
        --text-tertiary: #A89F94;
        --text-inverse: #FAF7F2;
        --border: #E8E2D9;
        --border-strong: #D4CCC0;
        --status-critical: #C8553D;
        --status-warning: #E8A04A;
        --status-healthy: #7FB77E;
        --status-under: #6B8CAE;
        --provider-aws: #D97757;
        --provider-gcp: #6B8CAE;
        --provider-azure: #8B7FB8;
        --radius-card: 20px;
        --radius-button: 12px;
        --radius-input: 10px;
        --radius-large: 28px;
        --shadow-subtle: 0 1px 2px rgba(0,0,0,0.04);
        --shadow-hover: 0 4px 12px rgba(0,0,0,0.06);
    }

    html, body, [class*="css"], .stApp {
        font-family: 'Inter', sans-serif !important;
        background-color: var(--bg-warm) !important;
        color: var(--text-primary) !important;
    }
    h1, h2 {
        font-family: 'Instrument Serif', serif !important;
        font-weight: 400 !important;
        letter-spacing: -0.02em !important;
        color: var(--text-primary) !important;
    }
    h3, h4, h5, h6 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-variant-numeric: tabular-nums !important;
    }
    [data-testid="stMetric"] {
        background: var(--bg-warm-subtle) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-card) !important;
        padding: 20px 24px !important;
        box-shadow: var(--shadow-subtle) !important;
    }
    .stButton > button {
        border-radius: var(--radius-button) !important;
        border: 1px solid var(--border-strong) !important;
        background: var(--bg-warm) !important;
        color: var(--text-primary) !important;
        font-weight: 500 !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        border-color: var(--text-primary) !important;
        box-shadow: var(--shadow-hover) !important;
        transform: translateY(-1px) !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important;
        border-bottom: 1px solid var(--border) !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-button) var(--radius-button) 0 0 !important;
        padding: 12px 20px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        color: var(--text-secondary) !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--text-primary) !important;
        border-bottom: 2px solid var(--provider-aws) !important;
    }
    [data-testid="stSidebar"] {
        background-color: var(--bg-warm-subtle) !important;
        border-right: 1px solid var(--border) !important;
    }
    .stDataFrame {
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-card) !important;
        overflow: hidden !important;
    }
    .stSelectbox > div > div {
        border-radius: var(--radius-input) !important;
        border-color: var(--border) !important;
        background-color: var(--bg-warm) !important;
    }
    </style>
    """, unsafe_allow_html=True)


_inject_design_system()


def _get_conn(readonly: bool = True) -> psycopg2.extensions.connection:
    conn = psycopg2.connect(_PG_DSN)
    conn.autocommit = True
    return conn


def _table_exists(conn: psycopg2.extensions.connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename=%s",
        [table],
    )
    exists = cur.fetchone() is not None
    cur.close()
    return exists


@st.cache_data(ttl=300)
def _query(sql: str, params: list[object] | None = None) -> list[dict[str, object]]:
    """PostgreSQL 쿼리 결과를 dict 리스트로 반환한다."""
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(sql, params or [])
        if cur.description is None:
            cur.close()
            conn.close()
            return []
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []


@st.cache_data(ttl=300)
def _available_months() -> list[str]:
    rows = _query(
        "SELECT DISTINCT to_char(charge_date, 'YYYY-MM') AS m "
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
st.sidebar.caption("Data source: PostgreSQL")

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_overview, tab_explorer, tab_anomaly, tab_forecast, tab_budget, tab_chargeback, tab_settings = st.tabs([
    "Overview",
    "Cost Explorer",
    "Anomalies",
    "Forecast",
    "Budget",
    "Chargeback",
    "Settings",
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
                SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS total_cost,
                COUNT(DISTINCT provider) AS providers,
                COUNT(DISTINCT cost_unit_key) AS cost_units
            FROM fact_daily_cost
            WHERE to_char(charge_date, 'YYYY-MM') = '{selected_month}'
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
                charge_date::TEXT,
                provider,
                SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS cost
            FROM fact_daily_cost
            WHERE to_char(charge_date, 'YYYY-MM') = '{selected_month}'
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
                SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS cost
            FROM fact_daily_cost
            WHERE to_char(charge_date, 'YYYY-MM') = '{selected_month}'
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
                SUM(CAST(effective_cost AS DOUBLE PRECISION)) AS cost,
                COUNT(DISTINCT resource_id) AS resources
            FROM fact_daily_cost
            WHERE to_char(charge_date, 'YYYY-MM') = '{selected_month}'
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
                charge_date::TEXT,
                CAST(effective_cost AS DOUBLE PRECISION) AS effective_cost,
                CAST(mean_cost AS DOUBLE PRECISION) AS mean_cost,
                CAST(z_score AS DOUBLE PRECISION) AS z_score,
                severity, detector_name
            FROM anomaly_scores
            WHERE to_char(charge_date, 'YYYY-MM') = '{selected_month}'
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
                color_discrete_map={
                    "critical": "#C8553D", "warning": "#E8A04A", "ok": "#7FB77E"
                },
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
            CAST(predicted_monthly_cost AS DOUBLE PRECISION) AS predicted,
            CAST(lower_bound_monthly_cost AS DOUBLE PRECISION) AS lower_bound,
            CAST(upper_bound_monthly_cost AS DOUBLE PRECISION) AS upper_bound,
            CAST(hourly_cost AS DOUBLE PRECISION) AS hourly_cost,
            model_trained_at::TEXT
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
                   CAST(forecast_monthly_cost AS DOUBLE PRECISION) AS forecast,
                   CAST(actual_monthly_cost AS DOUBLE PRECISION) AS actual,
                   CAST(variance_pct AS DOUBLE PRECISION) AS variance_pct
            FROM dim_forecast_variance_prophet
            ORDER BY ABS(variance_pct) DESC NULLS LAST
            LIMIT 50
        """ if not selected_month else f"""
            SELECT resource_id, status, billing_month,
                   CAST(forecast_monthly_cost AS DOUBLE PRECISION) AS forecast,
                   CAST(actual_monthly_cost AS DOUBLE PRECISION) AS actual,
                   CAST(variance_pct AS DOUBLE PRECISION) AS variance_pct
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
                    "within_bounds": "#7FB77E",
                    "above_upper": "#C8553D",
                    "below_lower": "#6B8CAE",
                    "no_actual": "#A89F94",
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

    budget_status = _query(
        "SELECT team, env, CAST(budget_amount AS DOUBLE PRECISION) AS budget_amount, "
        "CAST(actual_cost AS DOUBLE PRECISION) AS actual_cost, "
        "CAST(utilization_pct AS DOUBLE PRECISION) AS utilization_pct, status "
        "FROM dim_budget_status "
        "WHERE billing_month = %s "
        "ORDER BY utilization_pct DESC",
        [selected_month],
    ) if selected_month else []

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
            color_discrete_map={"over": "#C8553D", "warning": "#E8A04A", "ok": "#7FB77E"},
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
        "SELECT team, env, CAST(budget_amount AS DOUBLE PRECISION) AS budget_amount, "
        "billing_month, updated_at::TEXT "
        "FROM dim_budget ORDER BY team, env"
    )
    if budget_config:
        import pandas as pd
        st.dataframe(pd.DataFrame(budget_config), use_container_width=True)
    else:
        st.info("No budget configuration found.")

    st.subheader("Edit Budget")
    with st.expander("Add / Update Budget Entry"):
        with st.form("budget_edit_form"):
            col_team, col_env = st.columns(2)
            new_team = col_team.text_input("Team (* for all)", value="*")
            new_env = col_env.text_input("Env (* for all)", value="*")
            new_amount = st.number_input(
                "Monthly Budget (USD)", min_value=0.0, value=1000.0, step=100.0
            )
            new_month = st.text_input(
                "Billing Month (YYYY-MM, blank = all months)", value=""
            )
            submitted = st.form_submit_button("Save Budget")

        if submitted:
            try:
                conn = _get_conn(readonly=False)
                cur = conn.cursor()
                billing_month_val = new_month.strip() if new_month.strip() else None
                cur.execute(
                    "SELECT COUNT(*) FROM dim_budget WHERE team=%s AND env=%s",
                    [new_team, new_env],
                )
                existing = cur.fetchone()
                if existing and existing[0] > 0:
                    cur.execute(
                        "UPDATE dim_budget SET budget_amount=%s, billing_month=%s, "
                        "updated_at=NOW() WHERE team=%s AND env=%s",
                        [new_amount, billing_month_val, new_team, new_env],
                    )
                    st.success(f"Updated budget for {new_team}/{new_env}: ${new_amount:,.2f}")
                else:
                    cur.execute(
                        "INSERT INTO dim_budget (team, env, budget_amount, billing_month) "
                        "VALUES (%s, %s, %s, %s)",
                        [new_team, new_env, new_amount, billing_month_val],
                    )
                    st.success(f"Added budget for {new_team}/{new_env}: ${new_amount:,.2f}")
                cur.close()
                conn.close()
                st.cache_data.clear()
            except Exception as exc:
                st.error(f"Failed to save: {exc}")

    with st.expander("Delete Budget Entry"):
        del_entries = _query("SELECT team, env FROM dim_budget ORDER BY team, env")
        if del_entries:
            import pandas as pd
            del_options = [f"{r['team']}/{r['env']}" for r in del_entries]
            del_choice = st.selectbox("Select entry to delete", del_options)
            if st.button("Delete Selected Entry"):
                del_team, del_env = del_choice.split("/", 1)
                try:
                    conn = _get_conn(readonly=False)
                    cur = conn.cursor()
                    cur.execute(
                        "DELETE FROM dim_budget WHERE team=%s AND env=%s",
                        [del_team, del_env],
                    )
                    cur.close()
                    conn.close()
                    st.success(f"Deleted budget entry: {del_choice}")
                    st.cache_data.clear()
                except Exception as exc:
                    st.error(f"Failed to delete: {exc}")
        else:
            st.info("No budget entries to delete.")

# ── Tab 6: Chargeback ─────────────────────────────────────────────────────────

with tab_chargeback:
    st.header("Chargeback Report")
    if not selected_month:
        st.info("No data available.")
    else:
        cb_rows = _query(
            "SELECT provider, team, product, env, cost_unit_key, "
            "CAST(actual_cost AS DOUBLE PRECISION) AS actual_cost, "
            "CAST(budget_amount AS DOUBLE PRECISION) AS budget_amount, "
            "CAST(utilization_pct AS DOUBLE PRECISION) AS utilization_pct, "
            "resource_count "
            "FROM dim_chargeback "
            "WHERE billing_month = %s "
            "ORDER BY actual_cost DESC",
            [selected_month],
        )
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

# ── Tab 7: Settings ───────────────────────────────────────────────────────────

with tab_settings:
    st.header("Platform Settings")
    st.caption("PostgreSQL `platform_settings` 테이블의 런타임 임계값을 조회·수정합니다.")

    settings_rows = _query(
        "SELECT key, value, value_type, description, updated_at::TEXT "
        "FROM platform_settings ORDER BY key"
    )

    if not settings_rows:
        st.info(
            "platform_settings 테이블이 없습니다. "
            "Dagster에서 anomaly_detection 또는 다른 asset을 한 번 실행하세요."
        )
    else:
        import pandas as pd

        df_settings = pd.DataFrame(settings_rows)

        st.subheader("Active Detectors")
        active_row = next(
            (r for r in settings_rows if r["key"] == "anomaly.active_detectors"), None
        )
        if active_row:
            all_detectors = ["zscore", "isolation_forest", "moving_average", "arima", "autoencoder"]
            current_active = [d.strip() for d in str(active_row["value"]).split(",")]
            selected = st.multiselect(
                "활성 탐지기 선택",
                options=all_detectors,
                default=[d for d in current_active if d in all_detectors],
            )
            if st.button("탐지기 설정 저장"):
                new_value = ",".join(selected)
                try:
                    conn = _get_conn(readonly=False)
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE platform_settings SET value=%s WHERE key='anomaly.active_detectors'",
                        [new_value],
                    )
                    cur.close()
                    conn.close()
                    st.success(f"활성 탐지기 업데이트: {new_value}")
                    st.cache_data.clear()
                except Exception as exc:
                    st.error(f"저장 실패: {exc}")

        st.subheader("All Settings")
        st.dataframe(df_settings, use_container_width=True)

        st.subheader("Edit Setting")
        with st.expander("값 수정"):
            setting_keys = [r["key"] for r in settings_rows]
            selected_key = st.selectbox("설정 키", setting_keys)
            current_val = next(
                (r["value"] for r in settings_rows if r["key"] == selected_key), ""
            )
            new_val = st.text_input("새 값", value=str(current_val))
            if st.button("저장"):
                try:
                    conn = _get_conn(readonly=False)
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE platform_settings SET value=%s WHERE key=%s",
                        [new_val, selected_key],
                    )
                    cur.close()
                    conn.close()
                    st.success(f"{selected_key} = {new_val} 저장 완료")
                    st.cache_data.clear()
                except Exception as exc:
                    st.error(f"저장 실패: {exc}")

    st.subheader("Cost Recommendations")
    rec_rows = _query(
        "SELECT resource_id, team, env, provider, "
        "recommendation_type, reason, "
        "CAST(estimated_savings AS DOUBLE PRECISION) AS estimated_savings, severity "
        "FROM dim_cost_recommendations "
        "WHERE billing_month = %s "
        "ORDER BY severity DESC, estimated_savings DESC NULLS LAST",
        [selected_month],
    ) if selected_month else []

    if rec_rows:
        import pandas as pd
        df_rec = pd.DataFrame(rec_rows)
        critical_cnt = len(df_rec[df_rec["severity"] == "critical"])
        warning_cnt = len(df_rec[df_rec["severity"] == "warning"])
        c1, c2 = st.columns(2)
        c1.metric("Critical Recommendations", critical_cnt)
        c2.metric("Warning Recommendations", warning_cnt)
        st.dataframe(df_rec, use_container_width=True)
    else:
        st.info("No recommendations. Run cost_recommendations asset first.")
