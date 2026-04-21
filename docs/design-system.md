# FinOps Platform — Design System

> 이 문서는 FinOps Platform의 **단일 디자인 소스 오브 트루스**다.
> Streamlit 대시보드(`scripts/streamlit_app.py`)와 Next.js 랜딩페이지(`web/`) 양쪽 구현은
> 반드시 이 문서의 토큰만 사용한다. 소스 코드에 hex·px 값을 직접 쓰지 않는다.
>
> **작업 시작 전 이 문서를 먼저 읽을 것.** Streamlit 기본 테마·Plotly 기본 템플릿·
> shadcn 기본 스타일은 금지다. "modern", "clean", "sleek" 같은 모호한 형용사로
> 회귀하지 말고 아래 토큰 값 그대로 구현할 것.

---

## 1. Design Philosophy

### 1.1 Reference
Arc Browser의 디자인 언어를 차용하되 재무 도구의 **신뢰감**은 유지한다.
참고: Arc Browser, Linear, Vercel, Raycast, Aesop, Rauno Freiberg의 개인 사이트.

### 1.2 Core Principles
- **Warm, not cold** — 순수 흰색(#FFFFFF)과 순수 검정(#000000) 금지. 항상 살짝 따뜻한 톤.
- **Squircle over rectangle** — iOS 스타일 부드러운 코너. 20~28px radius 기본.
- **Border over shadow** — 1px 보더 + 미세한 soft shadow. 큰 그림자 금지.
- **Typography as hierarchy** — 제목 72~96px, 본문 14~16px의 극단적 대비.
- **Muted over saturated** — Bloomberg 터미널 느낌 금지. 데이터 색상은 한 단계 누른 채도.
- **Asymmetry over centering** — 히어로·레이아웃은 의도적 비대칭으로.

### 1.3 Tone for FinOps
재무 도구는 기본적으로 딱딱하다. 따뜻한 palette + 부드러운 shape로 긴장을 풀되,
숫자·차트의 시각적 위계는 엄격히 유지해 신뢰감을 잃지 않는다.

---

## 2. Tech Stack & Implementation

이 디자인 시스템은 두 가지 컨텍스트를 지원한다.

### A. Streamlit 웹 대시보드 (`scripts/streamlit_app.py`)
- Streamlit ≥1.35 + Plotly ≥5.0
- 커스텀 CSS는 `st.markdown(..., unsafe_allow_html=True)`로 주입
- 모든 스타일은 `_inject_design_system()` 단일 함수에 집중
- Plotly는 프로젝트 전용 template `"finops"` 정의 후 모든 차트에 `template="finops"` 적용
- Streamlit `config.toml`의 primaryColor·backgroundColor도 맞춰서 일관성 유지

### B. Next.js 랜딩페이지 (`web/`)
- Next.js ≥14 + Tailwind CSS
- CSS 변수는 `app/globals.css`에 이 문서의 토큰 그대로 정의
- shadcn/ui 기본 스타일 금지, 필요한 컴포넌트만 커스터마이징해 사용
- 단일 페이지 구조, Vercel 배포 전제

### 공통 원칙
- 폰트: Google Fonts CDN (`Montserrat`, `Inter`, `JetBrains Mono`)
- 아이콘: **Phosphor Icons** (duotone 스타일) 또는 인라인 SVG. **이모지 금지.**
- 모든 토큰은 CSS 변수로 주입, 하드코딩 금지.

---

## 3. Color Tokens

### 3.1 Base Palette

| Token | Hex | 용도 |
|---|---|---|
| `--bg-warm` | `#FAF7F2` | 기본 배경 (off-white, 순수 흰색 금지) |
| `--bg-warm-subtle` | `#F2EDE4` | 카드 배경, 섹션 구분 |
| `--bg-dark` | `#1A1714` | 다크 섹션 (warm black, 순수 검정 금지) |
| `--bg-dark-subtle` | `#26221E` | 다크 섹션 내 카드 |
| `--text-primary` | `#1A1714` | 본문 기본 텍스트 |
| `--text-secondary` | `#6B6560` | 보조 텍스트, 캡션 |
| `--text-tertiary` | `#A89F94` | 비활성·placeholder |
| `--text-inverse` | `#FAF7F2` | 다크 배경 위 텍스트 |
| `--border` | `#E8E2D9` | 기본 보더 (1px) |
| `--border-strong` | `#D4CCC0` | 강조 보더, 호버 상태 |

### 3.2 Brand Gradients

메시 그라데이션 블롭, 히어로 액센트, 주요 CTA에만 **제한적으로** 사용.
과하게 뿌리면 Arc 느낌이 죽는다.

| Token | Stops | 용도 |
|---|---|---|
| `--gradient-primary` | `#FF6B4A → #FFB84A → #FFD93D` | 히어로 blob, 주요 CTA |
| `--gradient-secondary` | `#A78BFA → #F9A8D4` | 세컨더리 악센트, 일부 카드 |
| `--gradient-mesh-blur` | 위 primary, blur(120px) | 히어로 배경 mesh gradient |

### 3.3 Semantic Color Mapping (FinOps 상태값)

**이 프로젝트 고유의 상태값 색상. Streamlit 대시보드·Plotly 차트·React 랜딩 모두 동일 사용.**

#### Anomaly Severity (`anomaly_scores.severity`)
| 상태 | Hex | 기준 |
|---|---|---|
| `critical` | `#C8553D` (deep coral) | z-score ≥ 3.0 또는 detector별 critical threshold |
| `warning` | `#E8A04A` (amber) | 2.0 ≤ z-score < 3.0 |
| `normal` | `#7FB77E` (sage green) | 정상 범위 |

#### Variance (`v_variance`, Infracost/Prophet 기준)
| 상태 | Hex | 기준 |
|---|---|---|
| `over` | `#C8553D` (deep coral) | `variance_pct ≥ +20%` |
| `under` | `#6B8CAE` (muted blue) | `variance_pct ≤ -20%` (과소예측/미사용) |
| `within_band` | `#7FB77E` (sage green) | ±20% 이내 |

#### Budget Status (`dim_budget_status`)
| 상태 | Hex | 기준 |
|---|---|---|
| `over` | `#C8553D` | `usage_pct ≥ 100%` |
| `warning` | `#E8A04A` | `usage_pct ≥ 80%` |
| `healthy` | `#7FB77E` | `usage_pct < 80%` |

### 3.4 Provider Palette (AWS / GCP / Azure)

**브랜드 원색(AWS 오렌지 `#FF9900`, GCP 파랑 `#4285F4`, Azure 파랑 `#0078D4`) 금지.**
그대로 쓰면 Bloomberg 터미널처럼 보여서 Arc 느낌이 완전히 죽는다.
정체성은 유지하되 채도를 낮춘 muted 값을 사용한다.

| Provider | Hex | 계열 |
|---|---|---|
| `aws` | `#D97757` | warm terracotta (오렌지의 muted 버전) |
| `gcp` | `#6B8CAE` | muted blue |
| `azure` | `#8B7FB8` | muted purple |

### 3.5 Data Visualization Palette

Plotly stacked chart, treemap 등에서 사용하는 범용 팔레트.
위 Provider 색상이 우선이며, 서비스·팀 구분 등 추가 범주가 필요할 때만 사용.
#7FB77E  sage green
#6B8CAE  muted blue
#D97757  warm terracotta
#8B7FB8  muted purple
#E8A04A  amber
#C8553D  deep coral
#A89F94  muted neutral
#5C8A7A  muted teal

### 3.6 금지 사항

- 순수 흰색 `#FFFFFF`, 순수 검정 `#000000` 사용 금지
- 브랜드 원색(AWS 오렌지, GCP 파랑, Azure 파랑) 직접 사용 금지
- Streamlit 기본 primaryColor(`#FF4B4B`) 사용 금지
- Plotly 기본 템플릿(`plotly`, `plotly_white`, `plotly_dark`) 그대로 사용 금지
- 보라·파랑 그라데이션 (AI 기본값) 금지

---

## 4. Typography

### 4.1 Font Stack

| Role | Font | Fallback |
|---|---|---|
| Display (큰 제목) | Montserrat | sans-serif |
| Subheading · Body · UI | Inter | sans-serif |
| Number · Money · Mono | JetBrains Mono | ui-monospace, monospace |

### 4.2 Scale

| Token | Size | Line Height | 용도 |
|---|---|---|---|
| `--text-display-xl` | 96px | 1.0 | 랜딩 히어로 헤드라인 |
| `--text-display-lg` | 72px | 1.05 | 섹션 메인 타이틀 |
| `--text-display-md` | 48px | 1.1 | 서브 섹션 타이틀 |
| `--text-h1` | 32px | 1.2 | Streamlit 페이지 제목 |
| `--text-h2` | 24px | 1.3 | 탭 제목, 카드 헤더 |
| `--text-h3` | 18px | 1.4 | 소제목 |
| `--text-body` | 16px | 1.6 | 본문 |
| `--text-body-sm` | 14px | 1.5 | UI 기본 (Streamlit 기본값) |
| `--text-caption` | 12px | 1.4 | 캡션, 범례, 라벨 |
| `--text-metric` | 48px | 1.0 | KPI 카드 큰 숫자 |

### 4.3 Weight

- Display (Montserrat): 600 (semi-bold)
- Heading (Inter): 500 또는 600
- Body (Inter): 400
- Mono (JetBrains Mono): 400 또는 500

### 4.4 Letter Spacing

- Display 크기 (48px+): `-0.02em` (살짝 타이트하게)
- Heading (18~32px): `-0.01em`
- Body: `0`
- Caption (12px): `+0.02em` (살짝 느슨하게, 가독성 확보)

### 4.5 Streamlit 주입 구현

`scripts/streamlit_app.py` 최상단에 정의하고 `main()` 시작 시 호출.

```python
def _inject_design_system() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        /* Base palette */
        --bg-warm: #FAF7F2;
        --bg-warm-subtle: #F2EDE4;
        --bg-dark: #1A1714;
        --text-primary: #1A1714;
        --text-secondary: #6B6560;
        --text-tertiary: #A89F94;
        --border: #E8E2D9;
        --border-strong: #D4CCC0;

        /* Semantic */
        --status-critical: #C8553D;
        --status-warning: #E8A04A;
        --status-healthy: #7FB77E;
        --status-under: #6B8CAE;

        /* Provider */
        --provider-aws: #D97757;
        --provider-gcp: #6B8CAE;
        --provider-azure: #8B7FB8;

        /* Shape */
        --radius-card: 20px;
        --radius-button: 12px;
        --radius-input: 10px;
        --radius-large: 28px;
    }

    html, body, [class*="css"], .stApp {
        font-family: 'Inter', sans-serif;
        background-color: var(--bg-warm);
        color: var(--text-primary);
    }
    h1, h2, .display-sans {
        font-family: 'Montserrat', sans-serif;
        font-weight: 400;
        letter-spacing: -0.02em;
    }
    h3, h4, h5 {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        letter-spacing: -0.01em;
    }
    [data-testid="stMetricValue"], .metric-value, .tabular-num {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
    }

    /* Cards */
    [data-testid="stMetric"] {
        background: var(--bg-warm-subtle);
        border: 1px solid var(--border);
        border-radius: var(--radius-card);
        padding: 20px 24px;
    }

    /* Buttons */
    .stButton > button {
        border-radius: var(--radius-button);
        border: 1px solid var(--border-strong);
        background: var(--bg-warm);
        color: var(--text-primary);
        font-weight: 500;
    }
    .stButton > button:hover {
        border-color: var(--text-primary);
        transform: translateY(-1px);
        transition: all 0.2s ease;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 1px solid var(--border);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-button) var(--radius-button) 0 0;
        padding: 12px 20px;
    }
    </style>
    """, unsafe_allow_html=True)
```

동시에 `.streamlit/config.toml`에도 베이스 색상 지정:

```toml
[theme]
primaryColor = "#D97757"
backgroundColor = "#FAF7F2"
secondaryBackgroundColor = "#F2EDE4"
textColor = "#1A1714"
font = "sans serif"
```

### 4.6 React 주입 구현

`web/app/globals.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg-warm: #FAF7F2;
  --bg-warm-subtle: #F2EDE4;
  --bg-dark: #1A1714;
  --text-primary: #1A1714;
  --text-secondary: #6B6560;
  --border: #E8E2D9;
  /* ... 위 Streamlit과 동일 세트 */
}

body {
  background-color: var(--bg-warm);
  color: var(--text-primary);
  font-family: 'Inter', sans-serif;
}

.font-display {
  font-family: 'Montserrat', sans-serif;
  letter-spacing: -0.02em;
}

.font-mono {
  font-family: 'JetBrains Mono', monospace;
  font-variant-numeric: tabular-nums;
}
```

`tailwind.config.ts`에도 토큰 매핑:

```ts
theme: {
  extend: {
    colors: {
      bg: { warm: '#FAF7F2', 'warm-subtle': '#F2EDE4', dark: '#1A1714' },
      text: { primary: '#1A1714', secondary: '#6B6560', tertiary: '#A89F94' },
      border: { DEFAULT: '#E8E2D9', strong: '#D4CCC0' },
      status: { critical: '#C8553D', warning: '#E8A04A', healthy: '#7FB77E', under: '#6B8CAE' },
      provider: { aws: '#D97757', gcp: '#6B8CAE', azure: '#8B7FB8' },
    },
    borderRadius: {
      card: '20px',
      button: '12px',
      input: '10px',
      large: '28px',
    },
    fontFamily: {
      display: ['"Montserrat"', 'sans-serif'],
      sans: ['Inter', 'sans-serif'],
      mono: ['"JetBrains Mono"', 'monospace'],
    },
  }
}
```

---

## 5. Shape Language

### 5.1 Border Radius

| Token | Value | 용도 |
|---|---|---|
| `--radius-input` | 10px | input, select, 작은 badge |
| `--radius-button` | 12px | 버튼, pill 아닌 것 |
| `--radius-card` | 20px | 카드, 메트릭 컨테이너, 차트 래퍼 |
| `--radius-large` | 28px | 히어로 섹션 대형 컨테이너, 모달 |
| `--radius-full` | 9999px | pill 버튼, avatar, toggle |

모든 코너는 **squircle** 지향 — CSS `border-radius`만으로 충분하지만 크기가 커질수록
더 부드럽게 보이도록 `cubic-bezier` hover 트랜지션과 함께 사용.

### 5.2 Shadow

큰 그림자 금지. 1px 보더 + 미세한 soft shadow 조합을 기본으로 한다.

| Token | Value | 용도 |
|---|---|---|
| `--shadow-subtle` | `0 1px 2px rgba(0,0,0,0.04)` | 기본 카드 |
| `--shadow-hover` | `0 4px 12px rgba(0,0,0,0.06)` | hover 상태 |
| `--shadow-float` | `0 8px 24px rgba(0,0,0,0.08)` | 드롭다운, popover |

### 5.3 Border

모든 보더는 `1px solid var(--border)`. 강조 시 `var(--border-strong)`.
다중 보더·점선·대시 보더는 사용하지 않는다.

---

## 6. Spacing & Layout

### 6.1 Spacing Scale (4px 기반)

`4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 120px`

### 6.2 Section Spacing

- 섹션 간 수직 여백: **120px 이상** (랜딩페이지)
- 대시보드 탭 내 블록 간: 32~48px
- 카드 내부 패딩: 20~24px
- 카드 간 gap: 16~20px

### 6.3 Container Width

- 랜딩페이지 max-width: `1280px`, 좌우 padding 24px (모바일) / 48px (데스크탑)
- 히어로 내 헤드라인 max-width: `720px`
- 본문 텍스트 max-width: `680px` (가독성)

### 6.4 Grid

랜딩페이지는 **의도적 비대칭**. CSS Grid로 `5fr 7fr` 또는 `7fr 5fr` 분할.
12컬럼 균등 그리드는 지양한다.

---

## 7. Iconography

- 라이브러리: **Phosphor Icons** (duotone 스타일 우선)
- 대체: 인라인 SVG (stroke-width 1.5px, 둥근 선단)
- 크기: 16px / 20px / 24px / 32px
- 색상: 기본 `currentColor` 상속
- **이모지 금지** — 탭 제목, 버튼, 메트릭 라벨 모두 해당

React: `phosphor-react` 또는 `@phosphor-icons/react`
Streamlit: Phosphor CDN을 HTML에서 로드 후 `<i class="ph-duotone ph-chart-line"></i>` 형태

---

## 8. Number Display Rules

`Decimal(18,6)` 타입 보존 + 시각적 위계 확보.

- **`$` 기호는 숫자보다 작게** — CSS `.currency-symbol { font-size: 0.7em; opacity: 0.8; }`
- **tabular-nums 필수** — JetBrains Mono 또는 Inter의 `font-variant-numeric: tabular-nums`
- **천 단위 구분자 항상 사용** — `$847,230.45`
- **소수점 자릿수:**
  - KPI·카드: 2자리 (`$847,230.45`)
  - 상세 테이블: 6자리까지 허용 (Decimal 원본 보존)
  - 퍼센트: 1자리 (`+12.3%`)
- **큰 금액 축약:**
  - 1,000,000 이상 → `$1.2M`
  - 1,000 이상 1M 미만 → 원본 그대로 `$847,230`
  - 소수점 이하 생략 가능한 경우 생략
- **증감 표시:** 이모지 대신 텍스트 화살표
  - 증가 (bad): `▲ +12.3%` in `var(--status-critical)`
  - 감소 (good): `▼ -8.1%` in `var(--status-healthy)`
  - 비용 맥락이므로 **증가가 bad**가 기본 — 상황에 따라 반전 가능 (예: 절감액은 증가가 good)

### 예시 렌더링

```html
<div class="metric-value font-mono">
  <span class="currency-symbol">$</span>847,230<span class="decimal">.45</span>
</div>
<div class="metric-delta text-status-critical">▲ +12.3% vs last month</div>
```

---

## 9. Plotly Template

모든 차트에 적용할 프로젝트 전용 template `"finops"`.
`scripts/streamlit_app.py`에 정의하고 import해서 사용.

```python
import plotly.graph_objects as go
import plotly.io as pio

FINOPS_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(
            family="Inter, sans-serif",
            size=13,
            color="#1A1714",
        ),
        paper_bgcolor="#FAF7F2",
        plot_bgcolor="#FAF7F2",
        colorway=[
            "#7FB77E",  # sage green
            "#6B8CAE",  # muted blue
            "#D97757",  # warm terracotta (AWS)
            "#8B7FB8",  # muted purple (Azure)
            "#E8A04A",  # amber
            "#C8553D",  # deep coral
            "#A89F94",  # muted neutral
            "#5C8A7A",  # muted teal
        ],
        xaxis=dict(
            gridcolor="#E8E2D9",
            linecolor="#D4CCC0",
            tickfont=dict(family="JetBrains Mono, monospace", size=11, color="#6B6560"),
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor="#E8E2D9",
            linecolor="#D4CCC0",
            tickfont=dict(family="JetBrains Mono, monospace", size=11, color="#6B6560"),
            zeroline=False,
        ),
        legend=dict(
            font=dict(family="Inter, sans-serif", size=12, color="#6B6560"),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
        ),
        margin=dict(l=48, r=24, t=32, b=48),
        hoverlabel=dict(
            bgcolor="#1A1714",
            bordercolor="#1A1714",
            font=dict(family="Inter, sans-serif", size=12, color="#FAF7F2"),
        ),
    )
)

pio.templates["finops"] = FINOPS_TEMPLATE
pio.templates.default = "finops"
```

모든 차트는 `fig.update_layout(template="finops")` 또는 default로 자동 적용.

---

## 10. Signature Charts (FinOps 고유 시각화)

### 10.1 Multi-Cloud Stacked Area (Overview 탭 메인)

- x축: 일자 (30일 lookback), y축: `effective_cost` 합계 (USD)
- stack: `provider` (aws/gcp/azure), Provider 색상 사용
- fill opacity: 0.3, stroke opacity: 1.0
- 코너 둥글게: `line_shape='spline'`
- 상단 legend, pill 형태 토글

### 10.2 Anomaly Scatter (Anomalies 탭)

- x축: 일자, y축: `effective_cost`
- 일반 점: `#A89F94` muted neutral, size=6, opacity=0.5
- `warning`: `#E8A04A`, size=10, opacity=0.9
- `critical`: `#C8553D`, size=14, 외곽 ring (stroke 2px white)
- hover: `resource_id` + z-score + `detector_name` + cost_unit_key

### 10.3 Budget Gauge Cards (Budget 탭)

- 각 `(team, env)` 조합마다 pill 형태 카드
- `border-radius: var(--radius-card)`, `1px solid var(--border)`
- 상단: 팀명 (Inter 14px, secondary color)
- 중앙: 사용금액 (JetBrains Mono 32px, `--text-metric` 스케일)
- 하단: budget cap + usage_pct
- 내부 progress bar: 색상은 Budget Status 매핑

### 10.4 Chargeback Treemap (Chargeback 탭)

- 계층: `team` → `product` → `env`
- 타일 색상: team 기준 Data Viz Palette 순환
- 타일 크기: `effective_cost` 비례
- 타일 border: 2px `--bg-warm` (카드 분리감)
- 라벨: 팀명 Inter 600, 금액 JetBrains Mono

### 10.5 Variance Bar (Forecast 탭)

- 가로 bar chart, 리소스별 `variance_pct`
- `over`: `--status-critical`
- `under`: `--status-under`
- `within_band`: `--status-healthy`
- y축: resource_id, x축: variance_pct (0 기준선)

---

## 11. Landing Page Composition (Next.js `web/`)

### 11.1 Page Sections (상단→하단)

1. **Hero** — 비대칭 5fr/7fr, 좌측 Montserrat 헤드라인 + 우측 라이브 대시보드 프리뷰
2. **Five Core Questions** — CLAUDE.md 섹션 1의 5개 질문을 카드로 (squircle 20px, 1px border)
3. **Multi-Cloud Native** — AWS/GCP/Azure 통합을 시각적으로 강조 (가장 큰 차별점)
4. **Detection Arsenal** — 5개 탐지기(Z-score·IsolationForest·MovingAverage·ARIMA·Autoencoder) 그리드
5. **Architecture Diagram** — Medallion 파이프라인 (Dagster → Iceberg → DuckDB → Streamlit)
6. **Get Started** — 3줄 설치 코드 + GitHub 링크 (CTA)
7. **Footer** — Apache 2.0 license, GitHub, 기여 가이드

### 11.2 Hero Guidelines

- 헤드라인: `"See where your cloud money really goes"` 수준의 직설적 copy
- Montserrat 96px, max-width 720px
- 서브 카피: Inter 18px, `--text-secondary`, max-width 540px
- CTA 2개: primary(`Get Started` — dark button) + secondary(`View on GitHub` — outline)
- 배경: `--gradient-mesh-blur` blob, opacity 0.6, blur(120px)

### 11.3 Live Dashboard Preview

히어로 우측에 실제 대시보드 미니어처를 SVG 또는 React 컴포넌트로 삽입.
반드시 포함할 요소:
- 작은 stacked area chart (multi-cloud)
- Top-3 cost driver 리스트 (금액 JetBrains Mono)
- 1-2개 anomaly pill badge
- 카드 자체는 `--radius-large` 28px, 미세 tilt 또는 shadow-float

---

## 12. Open Source Assets

오픈소스 배포 시 첫인상을 책임지는 자산들.

### 12.1 OG Image (소셜 공유)

- 크기: 1200×630px
- 배경: `--bg-warm` + mesh gradient blob
- 좌측: Montserrat 헤드라인 (프로젝트명 + tagline)
- 우측: 대시보드 프리뷰 또는 architecture 다이어그램
- `public/og.png`로 저장, `<meta property="og:image">` 지정

### 12.2 README 호환성

GitHub README는 light/dark mode 모두 대응해야 함.

```markdown
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/screenshots/hero-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="./docs/screenshots/hero-light.png">
  <img alt="FinOps Platform" src="./docs/screenshots/hero-light.png">
</picture>
```

- 로고·배지·히어로 스크린샷 모두 두 모드 버전 준비
- 배지 색상: shields.io의 `color=` 파라미터를 토큰 hex로 커스텀 (기본 초록 금지)

### 12.3 Screenshots (`docs/screenshots/`)

- 해상도: 2x 레티나 (실제 크기의 2배 캡처 후 표시는 1배)
- 6개 탭 각각 최소 1장 + 히어로 overview 1장
- 브라우저 chrome 제거, 내용만 캡처
- 파일명: `tab-{name}-{light|dark}.png`

---

## 13. Anti-Patterns (금지 리스트)

작업 중 다음이 나오면 즉시 수정.

- [ ] 순수 `#FFFFFF` 또는 `#000000` 사용
- [ ] AWS 오렌지/GCP 파랑/Azure 파랑 원색 직접 사용
- [ ] Streamlit 기본 primaryColor `#FF4B4B` 사용
- [ ] Plotly 기본 템플릿 (`plotly`, `plotly_dark`) 그대로 사용
- [ ] 이모지를 아이콘으로 사용 (탭 제목, 버튼 포함)
- [ ] 보라·파랑 그라데이션 (AI 기본 아웃풋 톤)
- [ ] 박스 그림자 큰 값 (`blur(20px)` 이상)
- [ ] 날카로운 직각 코너 (`border-radius: 0` 또는 `4px` 이하)
- [ ] 중앙 정렬만 쓴 히어로 레이아웃
- [ ] `Helvetica`, `Arial`, `Times New Roman` 같은 시스템 폰트 의존
- [ ] 금액에 `font-variant-numeric: tabular-nums` 누락
- [ ] `$` 기호가 숫자와 같은 크기
- [ ] shadcn/ui 컴포넌트를 기본 스타일 그대로 사용
- [ ] "modern", "clean", "sleek", "beautiful" 같은 프롬프트로 회귀

---

## 14. Reference Inspirations

구현 중 방향성 확인용 참고 사이트:

- **Arc Browser** (arc.net) — warm palette, squircle, 전반적 mood의 기준
- **Linear** (linear.app) — typography 위계, dashboard UI 밀도
- **Vercel** (vercel.com) — 랜딩페이지 구조, code block 디자인
- **Raycast** (raycast.com) — 아이콘 시스템, 다크모드 처리
- **Aesop** (aesop.com) — 세리프 타이포그래피 활용
- **Rauno Freiberg** (rauno.me) — 마이크로인터랙션, 디테일
- **Infracost** (infracost.io) — 동일 도메인 오픈소스의 벤치마크
- **Plausible Analytics** (plausible.io) — 오픈소스 랜딩 구조 모범