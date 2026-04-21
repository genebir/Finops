# FinOps Dashboard — UI Component Guide

> **Single source of truth** for Next.js 14 dashboard (`web-app/`) component usage, design tokens, and consistency rules.  
> 모든 신규 페이지는 이 문서의 패턴을 따라야 한다.

---

## 1. CSS Design Tokens

`web-app/app/globals.css`에 정의된 변수만 사용한다. 절대 하드코딩하지 않는다.

| Token | Value | Usage |
|---|---|---|
| `--bg-warm` | `#faf7f2` | 페이지 배경 |
| `--bg-warm-subtle` | `#f2ede4` | 카드 배경 (`Card` 컴포넌트) |
| `--text-primary` | `#1a1714` | 주요 텍스트, 숫자 |
| `--text-secondary` | `#6b6560` | 보조 텍스트 |
| `--text-tertiary` | `#a89f94` | 비활성 텍스트, 힌트 |
| `--border` | `#e8e2d9` | 구분선, 바 배경 |
| `--status-critical` | `#c8553d` | 위험/에러/초과 |
| `--status-warning` | `#e8a04a` | 경고 |
| `--status-healthy` | `#7fb77e` | 정상/성공/절감 |
| `--status-under` | `#6b8cae` | under 상태 |
| `--provider-aws` | `#d97757` | AWS 브랜드 (muted) |
| `--provider-gcp` | `#6b8cae` | GCP 브랜드 (muted) |
| `--provider-azure` | `#8b7fb8` | Azure 브랜드 (muted) |
| `--radius-card` | `20px` | 카드 테두리 |
| `--radius-button` | `12px` | 버튼/배지 테두리 |
| `--radius-full` | `9999px` | pill 배지 |

### ❌ 절대 사용 금지
```
var(--bg-card)      → var(--bg-warm-subtle) 사용
var(--text-muted)   → var(--text-secondary) 또는 var(--text-tertiary)
var(--font-mono)    → className="font-mono" 또는 fontFamily: "JetBrains Mono, monospace"
var(--accent)       → 해당 상태 변수(--status-critical 등) 사용
#2E2A26             → var(--border) (바 배경)
```

---

## 2. Typography Classes

| Class | Font | Usage |
|---|---|---|
| `font-display` | Montserrat 600 | 페이지 제목 (h1) |
| `font-mono` | JetBrains Mono | 금액, 숫자, 코드 |
| `currency-symbol` | 0.7em, opacity 0.8 | `$` 기호 (숫자보다 작게) |

```tsx
// 제목
<h1 className="font-display" style={{ fontSize: "28px", ... }}>

// 금액
<span className="font-mono">
  <span className="currency-symbol">$</span>
  {amount.toLocaleString()}
</span>

// 코드
<code className="font-mono" style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
  {resourceId}
</code>
```

---

## 3. Component 사용 규칙

### 3.1 PageHeader — 모든 페이지 최상단 필수

```tsx
import PageHeader from "@/components/layout/PageHeader";

<PageHeader
  title="Page Name"
  description="subtitle — context info"
  action={<SomeButton />}  // optional
/>
```

- `fontSize: 28px`, `font-display` (Montserrat 600)
- description: `fontSize: 14px`, `var(--text-secondary)`

### 3.2 Card + CardHeader — 섹션 컨테이너

```tsx
import { Card, CardHeader, SectionLabel } from "@/components/primitives/Card";

<Card>
  <CardHeader>Section Title</CardHeader>
  {/* content */}
</Card>

<Card style={{ marginBottom: "24px" }}>  {/* 간격 */}
```

- `CardHeader`: Inter 13px 600, `--text-primary`, marginBottom 20px
- `SectionLabel`: Inter 11px 600, `--text-tertiary`, uppercase

### 3.3 MetricCard — KPI 카드

```tsx
import { MetricCard } from "@/components/primitives/MetricCard";

<div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
  <MetricCard label="Total Cost" value="$12,345" sub="this month" />
  <MetricCard label="Critical" value="5" valueColor="var(--status-critical)" />
  <MetricCard label="MoM Change" value="+12%" delta={{ value: 12, context: "cost" }} />
</div>
```

- value: JetBrains Mono 32px, fontWeight 500
- 그리드: 4열 기본, 3열/2열 허용

### 3.4 SeverityBadge + ProviderBadge — 상태/프로바이더 표시

```tsx
import { SeverityBadge, ProviderBadge } from "@/components/status/SeverityBadge";

<SeverityBadge severity="critical" />  // critical|warning|healthy|over|under|ok|prod|staging|dev
<ProviderBadge provider="aws" />       // aws|gcp|azure
```

### 3.5 ErrorState + EmptyState — 에러/빈 상태

```tsx
import { ErrorState, EmptyState } from "@/components/primitives/States";

// 에러: fetch 실패 시
try { data = await api.xxx(); }
catch (e) { return <ErrorState message={String(e)} />; }

// 데이터 없음
{items.length === 0 && (
  <EmptyState title="No data" description="Run the xxx asset in Dagster." />
)}
```

---

## 4. Standard Table Pattern

**모든 테이블은 이 패턴을 정확히 따른다.**

```tsx
const HEADERS = ["Column1", "Column2", "Column3"];

<table style={{ width: "100%", borderCollapse: "collapse" }}>
  <thead>
    <tr>
      {HEADERS.map((h, idx, arr) => (
        <th key={h} style={{
          // 텍스트 정렬: 첫 열/텍스트=left, 금액/수치=right, 배지=center
          textAlign: "left",
          fontSize: "10px",
          fontWeight: 600,
          fontFamily: "Inter, sans-serif",
          color: "var(--text-tertiary)",
          letterSpacing: "0.07em",
          textTransform: "uppercase",
          // padding 패턴 (반드시 준수)
          padding: idx === 0
            ? "0 8px 12px 0"
            : idx === arr.length - 1
            ? "0 0 12px 8px"
            : "0 8px 12px 8px",
          borderBottom: "1px solid var(--border)",
        }}>
          {h}
        </th>
      ))}
    </tr>
  </thead>
  <tbody>
    {rows.map((row, i, arr) => (
      <tr key={row.id} style={{
        borderBottom: i < arr.length - 1 ? "1px solid var(--border)" : "none",
      }}>
        {/* 첫 번째 열 */}
        <td style={{ padding: "10px 0", fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
          {row.name}
        </td>
        {/* 중간 열 */}
        <td style={{ padding: "10px 8px", fontSize: "13px", color: "var(--text-secondary)" }}>
          {row.label}
        </td>
        {/* 마지막 열 */}
        <td style={{ padding: "10px 0 10px 8px", textAlign: "right" }}>
          <span className="font-mono" style={{ fontSize: "13px", color: "var(--text-primary)" }}>
            ${row.cost.toLocaleString()}
          </span>
        </td>
      </tr>
    ))}
  </tbody>
</table>
```

### 테이블 내 금액 표시
```tsx
<span className="font-mono" style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-primary)" }}>
  <span className="currency-symbol">$</span>
  {Math.round(cost).toLocaleString("en-US")}
</span>
```

### 테이블 내 코드/리소스 ID
```tsx
<code className="font-mono" style={{ fontSize: "11px", color: "var(--text-primary)" }}>
  {resourceId}
</code>
```

---

## 5. Badge / Pill 패턴

### 상태 배지 (SeverityBadge)
```tsx
<SeverityBadge severity="critical" />
```

### 커스텀 컬러 배지
```tsx
// color-mix로 배경 생성 (일관성 유지)
<span style={{
  display: "inline-block",
  padding: "2px 8px",
  borderRadius: "var(--radius-full)",  // pill
  fontSize: "10px",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "var(--status-critical)",
  background: "color-mix(in srgb, var(--status-critical) 15%, transparent)",
  border: "1px solid color-mix(in srgb, var(--status-critical) 30%, transparent)",
}}>
  CRITICAL
</span>
```

### 프로바이더 배지
```tsx
<ProviderBadge provider="aws" />
```

---

## 6. 진행률 바 패턴

```tsx
function ProgressBar({ pct, color = "var(--status-healthy)" }: { pct: number; color?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{
        flex: 1,
        height: "6px",
        borderRadius: "3px",
        backgroundColor: "var(--border)",  // 바탕: 항상 --border
        overflow: "hidden",
      }}>
        <div style={{
          width: `${Math.min(pct, 100)}%`,
          height: "100%",
          backgroundColor: color,
          borderRadius: "3px",
        }} />
      </div>
      <span className="font-mono" style={{ fontSize: "12px", color: "var(--text-secondary)", width: "38px", textAlign: "right" }}>
        {pct.toFixed(1)}%
      </span>
    </div>
  );
}
```

---

## 7. 페이지 구조 템플릿

```tsx
import PageHeader from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/primitives/Card";
import { MetricCard } from "@/components/primitives/MetricCard";
import { ErrorState, EmptyState } from "@/components/primitives/States";
import { SeverityBadge, ProviderBadge } from "@/components/status/SeverityBadge";
import { API_BASE, api } from "@/lib/api";

export const dynamic = "force-dynamic";  // 실시간 데이터 필요 시

export default async function MyPage() {
  let data;
  try { data = await api.myEndpoint(); }
  catch (e) { return <ErrorState message={String(e)} />; }

  return (
    <div style={{ maxWidth: "1200px" }}>
      <PageHeader
        title="Page Title"
        description={`${data.billing_month} — context`}
      />

      {/* KPI 그리드 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "16px", marginBottom: "32px" }}>
        <MetricCard label="Metric" value="$1,234" />
        <MetricCard label="Count" value="42" valueColor="var(--status-critical)" />
      </div>

      {/* 메인 콘텐츠 카드 */}
      <Card style={{ marginBottom: "24px" }}>
        <CardHeader>Section Title</CardHeader>
        {data.items.length === 0
          ? <EmptyState title="No data" description="Run the xxx asset." />
          : (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              {/* standard table pattern */}
            </table>
          )
        }
      </Card>
    </div>
  );
}
```

---

## 8. Sidebar 구조

`web-app/components/layout/Sidebar.tsx`에서 관리.

| 그룹 | 페이지 |
|---|---|
| (Pinned) Overview | `/overview` |
| Costs | cost-explorer, cloud-compare, services, leaderboard, env-breakdown |
| Anomalies | anomalies, anomaly-timeline, risk |
| Budget | budget, budget-forecast, burn-rate, savings, chargeback, showback, recommendations |
| Compliance | tag-compliance, tag-policy, inventory, data-quality |
| Operations | forecast, alerts, ops |
| (Bottom) Settings | `/settings` |

**새 페이지 추가 시:** `GROUPS` 배열에서 해당 카테고리에 `{ href, label, Icon }` 항목 추가. `Icon`은 `@phosphor-icons/react`에서 확인 후 사용.

---

## 9. 색상 사용 규칙 요약

| 상황 | 색상 |
|---|---|
| 위험/초과/에러 | `var(--status-critical)` |
| 경고/주의 | `var(--status-warning)` |
| 정상/절감/성공 | `var(--status-healthy)` |
| AWS | `var(--provider-aws)` |
| GCP | `var(--provider-gcp)` |
| Azure | `var(--provider-azure)` |
| prod 환경 | `#D97757` (--provider-aws와 동일) |
| staging 환경 | `#8E7BB5` |
| dev 환경 | `#5B9BD5` |
| 진행률 바 배경 | `var(--border)` |
| 카드 배경 | `var(--bg-warm-subtle)` |

---

## 10. 금지 패턴

```tsx
// ❌ 절대 금지
style={{ color: "#D97757" }}           // 하드코딩 금지 → var(--provider-aws)
style={{ background: "#2E2A26" }}      // 하드코딩 금지 → var(--border)
style={{ fontFamily: "var(--font-mono)" }}  // 존재하지 않는 변수
var(--bg-card)                          // 존재하지 않는 변수
var(--text-muted)                       // 존재하지 않는 변수
var(--accent)                           // 존재하지 않는 변수

// ❌ 인라인 h1 스타일 직접 작성 금지
<h1 style={{ fontSize: "22px", fontWeight: 700, ... }}>  // PageHeader 사용

// ❌ 커스텀 카드 div 금지
<div style={{ background: "var(--bg-warm-subtle)", borderRadius: "12px", ... }}>  // Card 컴포넌트 사용

// ✅ 올바른 패턴
<PageHeader title="My Page" />
<Card><CardHeader>Section</CardHeader></Card>
<MetricCard label="Total" value="$1,234" />
style={{ color: "var(--status-critical)" }}
style={{ backgroundColor: "var(--border)" }}  // 바 배경
```
