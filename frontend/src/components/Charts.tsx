import type { BatchAggregate, TimePoint } from "../api";

type NumericKey = "gdp_index" | "inflation" | "unemployment" | "policy_rate" | "bank_credit" | "bank_capital_ratio" | "net_exports" | "household_debt" | "productive_capital" | "business_investment" | "labor_force_participation" | "job_finding_rate" | "job_separation_rate";

const colors = ["#38bdf8", "#f59e0b", "#34d399", "#a78bfa"];

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function TimeSeriesChart({
  data,
  series,
  title,
  height = 240
}: {
  data: TimePoint[];
  series: Array<{ key: NumericKey; label: string }>;
  title: string;
  height?: number;
}) {
  const width = 760;
  const pad = { left: 54, right: 18, top: 24, bottom: 36 };
  const values = data.flatMap((row) => series.map((item) => finite(row[item.key])).filter((v): v is number => v !== null));
  if (!data.length || !values.length) return null;
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (Math.abs(max - min) < 1e-9) { min -= 1; max += 1; }
  const margin = (max - min) * 0.08;
  min -= margin; max += margin;
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const x = (index: number) => pad.left + (data.length <= 1 ? 0 : (index / (data.length - 1)) * innerW);
  const y = (value: number) => pad.top + ((max - value) / (max - min)) * innerH;
  const ticks = 4;

  return (
    <div className="chartCard">
      <div className="chartHeader">
        <strong>{title}</strong>
        <div className="chartLegend">
          {series.map((item, index) => <span key={item.key}><i style={{ background: colors[index % colors.length] }} />{item.label}</span>)}
        </div>
      </div>
      <svg className="chartSvg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        {Array.from({ length: ticks + 1 }).map((_, index) => {
          const yy = pad.top + (index / ticks) * innerH;
          const value = max - (index / ticks) * (max - min);
          return <g key={index}><line x1={pad.left} x2={width - pad.right} y1={yy} y2={yy} className="gridLine"/><text x={pad.left - 8} y={yy + 4} className="axisText" textAnchor="end">{value.toFixed(1)}</text></g>;
        })}
        <line x1={pad.left} x2={pad.left} y1={pad.top} y2={height - pad.bottom} className="axisLine" />
        <line x1={pad.left} x2={width - pad.right} y1={height - pad.bottom} y2={height - pad.bottom} className="axisLine" />
        {series.map((item, seriesIndex) => {
          const points = data.map((row, index) => {
            const value = finite(row[item.key]);
            return value === null ? null : `${x(index)},${y(value)}`;
          }).filter(Boolean).join(" ");
          return <polyline key={item.key} points={points} fill="none" stroke={colors[seriesIndex % colors.length]} strokeWidth="2.5" vectorEffect="non-scaling-stroke" />;
        })}
        <text x={pad.left} y={height - 10} className="axisText">Mês 1</text>
        <text x={width - pad.right} y={height - 10} className="axisText" textAnchor="end">Mês {data[data.length - 1].month}</text>
      </svg>
    </div>
  );
}

export function BatchBarChart({ data, title }: { data: BatchAggregate[]; title: string }) {
  if (!data.length) return null;
  const width = 760, height = 250;
  const pad = { left: 52, right: 18, top: 20, bottom: 45 };
  const max = Math.max(...data.map((row) => row.mean_gdp_index), 1);
  const min = Math.min(...data.map((row) => row.mean_gdp_index), 0);
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const range = Math.max(1e-9, max - min);
  const slot = innerW / data.length;
  const barW = Math.max(12, slot * 0.62);
  const y = (value: number) => pad.top + ((max - value) / range) * innerH;
  const baseline = y(Math.max(min, 0));
  return (
    <div className="chartCard">
      <div className="chartHeader"><strong>{title}</strong><span className="muted">PIB final médio</span></div>
      <svg className="chartSvg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        <line x1={pad.left} x2={width - pad.right} y1={baseline} y2={baseline} className="axisLine" />
        {data.map((row, index) => {
          const bx = pad.left + slot * index + (slot - barW) / 2;
          const by = y(row.mean_gdp_index);
          const bh = Math.max(1, Math.abs(baseline - by));
          return <g key={row.axis_value}>
            <rect x={bx} y={Math.min(by, baseline)} width={barW} height={bh} rx="5" className="batchBar" />
            <text x={bx + barW / 2} y={height - 20} textAnchor="middle" className="axisText">{row.axis_value}</text>
            <text x={bx + barW / 2} y={Math.max(14, Math.min(by, baseline) - 6)} textAnchor="middle" className="axisText">{row.mean_gdp_index.toFixed(1)}</text>
          </g>;
        })}
      </svg>
    </div>
  );
}
