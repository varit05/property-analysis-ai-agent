import type { ChartSeries } from "./types/types";

interface ChartViewProps {
  series: ChartSeries[];
}

/** Simple SVG-based chart renderer for line, bar, and pie charts. */
export function ChartView({ series }: Readonly<ChartViewProps>) {
  if (series.length === 0) return null;

  return (
    <div className="pa-chart-container">
      {series.map((s, i) => (
        <div className="pa-chart" key={s.name + i}>
          <div className="pa-chart-title">{s.name}</div>
          {s.chart_type === "line" && <LineChart series={s} />}
          {s.chart_type === "bar" && <BarChart series={s} />}
          {s.chart_type === "pie" && <PieChart series={s} />}
        </div>
      ))}
    </div>
  );
}

/* ── Line Chart ──────────────────────────────────────────────────── */

const CHART_W = 320;
const CHART_H = 200;
const PAD = { top: 10, right: 10, bottom: 30, left: 40 };
const PLOT_W = CHART_W - PAD.left - PAD.right;
const PLOT_H = CHART_H - PAD.top - PAD.bottom;

function LineChart({ series }: Readonly<{ series: ChartSeries }>) {
  const values = series.data.map((d) => d.value);
  const labels = series.data.map((d) => d.label);
  const maxVal = Math.max(...values, 1);
  const minVal = Math.min(...values, 0);
  const range = maxVal - minVal || 1;

  const points = values
    .map((v, i) => {
      const x = PAD.left + (i / Math.max(values.length - 1, 1)) * PLOT_W;
      const y = PAD.top + PLOT_H - ((v - minVal) / range) * PLOT_H;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={CHART_W} height={CHART_H} viewBox={`0 0 ${CHART_W} ${CHART_H}`}>
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
        const y = PAD.top + PLOT_H - frac * PLOT_H;
        return (
          <g key={frac}>
            <line
              x1={PAD.left}
              y1={y}
              x2={CHART_W - PAD.right}
              y2={y}
              stroke="var(--border, #e5e4e7)"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 4}
              y={y + 4}
              textAnchor="end"
              fill="var(--text, #6b6375)"
              fontSize={10}
            >
              {(minVal + frac * range).toFixed(0)}
            </text>
          </g>
        );
      })}

      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke="var(--accent, #aa3bff)"
        strokeWidth={2}
      />

      {/* Dots */}
      {values.map((v, i) => {
        const x = PAD.left + (i / Math.max(values.length - 1, 1)) * PLOT_W;
        const y = PAD.top + PLOT_H - ((v - minVal) / range) * PLOT_H;
        return (
          <circle key={i} cx={x} cy={y} r={3} fill="var(--accent, #aa3bff)" />
        );
      })}

      {/* X-axis labels */}
      {labels.map((label, i) => {
        const x = PAD.left + (i / Math.max(labels.length - 1, 1)) * PLOT_W;
        const show =
          labels.length <= 8 || i % Math.ceil(labels.length / 8) === 0;
        return show ? (
          <text
            key={i}
            x={x}
            y={CHART_H - 8}
            textAnchor="end"
            transform={`rotate(-30, ${x}, ${CHART_H - 8})`}
            fill="var(--text, #6b6375)"
            fontSize={10}
          >
            {label}
          </text>
        ) : null;
      })}
    </svg>
  );
}

/* ── Bar Chart ───────────────────────────────────────────────────── */

function BarChart({ series }: { series: ChartSeries }) {
  const values = series.data.map((d) => d.value);
  const labels = series.data.map((d) => d.label);
  const maxVal = Math.max(...values, 1);
  const barW = Math.max(4, PLOT_W / values.length - 4);

  return (
    <svg width={CHART_W} height={CHART_H} viewBox={`0 0 ${CHART_W} ${CHART_H}`}>
      {/* Baseline */}
      <line
        x1={PAD.left}
        y1={PAD.top + PLOT_H}
        x2={CHART_W - PAD.right}
        y2={PAD.top + PLOT_H}
        stroke="var(--border, #e5e4e7)"
        strokeWidth={1}
      />

      {values.map((v, i) => {
        const x = PAD.left + (i / values.length) * PLOT_W + 2;
        const barH = (v / maxVal) * PLOT_H;
        const y = PAD.top + PLOT_H - barH;
        return (
          <g key={i}>
            <rect
              x={x}
              y={y}
              width={barW}
              height={barH}
              fill="var(--accent, #aa3bff)"
              rx={2}
            />
            {labels.length <= 12 && (
              <text
                x={x + barW / 2}
                y={CHART_H - 8}
                textAnchor="end"
                transform={`rotate(-30, ${x + barW / 2}, ${CHART_H - 8})`}
                fill="var(--text, #6b6375)"
                fontSize={10}
              >
                {labels[i]}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

/* ── Pie Chart ───────────────────────────────────────────────────── */

const PIE_CX = CHART_W / 2;
const PIE_CY = CHART_H / 2;
const PIE_R = 70;

const PIE_COLORS = [
  "var(--accent, #aa3bff)",
  "#16a34a",
  "#dc2626",
  "#f59e0b",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
];

function PieChart({ series }: { series: ChartSeries }) {
  const total = series.data.reduce((s, d) => s + d.value, 0) || 1;

  const slices: Array<{
    path: string;
    color: string;
    label: string;
    lx: number;
    ly: number;
  }> = [];
  let currentAngle = 0;
  for (let i = 0; i < series.data.length; i++) {
    const d = series.data[i];
    const angle = (d.value / total) * 360;
    const startAngle = currentAngle;
    currentAngle += angle;
    const endAngle = currentAngle;

    const startRad = ((startAngle - 90) * Math.PI) / 180;
    const endRad = ((endAngle - 90) * Math.PI) / 180;

    const x1 = PIE_CX + PIE_R * Math.cos(startRad);
    const y1 = PIE_CY + PIE_R * Math.sin(startRad);
    const x2 = PIE_CX + PIE_R * Math.cos(endRad);
    const y2 = PIE_CY + PIE_R * Math.sin(endRad);

    const largeArc = angle > 180 ? 1 : 0;
    const path = `M ${PIE_CX} ${PIE_CY} L ${x1} ${y1} A ${PIE_R} ${PIE_R} 0 ${largeArc} 1 ${x2} ${y2} Z`;

    const midAngle = startAngle + angle / 2;
    const midRad = ((midAngle - 90) * Math.PI) / 180;
    const labelR = PIE_R * 0.65;
    const lx = PIE_CX + labelR * Math.cos(midRad);
    const ly = PIE_CY + labelR * Math.sin(midRad);

    slices.push({
      path,
      color: PIE_COLORS[i % PIE_COLORS.length],
      label: d.label,
      lx,
      ly,
    });
  }

  return (
    <svg
      width={CHART_W}
      height={CHART_H + 30}
      viewBox={`0 0 ${CHART_W} ${CHART_H + 30}`}
    >
      {slices.map((s, i) => (
        <g key={i}>
          <path
            d={s.path}
            fill={s.color}
            stroke="var(--bg, #fff)"
            strokeWidth={2}
          />
          {total > 0 && series.data[i].value / total > 0.05 && (
            <text
              x={s.lx}
              y={s.ly}
              textAnchor="middle"
              fill="#fff"
              fontSize={10}
              fontWeight={600}
            >
              {((series.data[i].value / total) * 100).toFixed(0)}%
            </text>
          )}
        </g>
      ))}
      {/* Legend */}
      {slices.map((s, i) => (
        <g key={`legend-${i}`} transform={`translate(0, ${CHART_H + 4})`}>
          <rect x={i * 80} y={0} width={10} height={10} fill={s.color} rx={2} />
          <text x={i * 80 + 14} y={9} fill="var(--text, #6b6375)" fontSize={10}>
            {s.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
