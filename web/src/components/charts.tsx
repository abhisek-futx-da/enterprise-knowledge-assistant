/** Hand-drawn SVG charts: a segmented arc dial and a small column chart. */

export interface Segment { value: number; color: string; label: string }

export function Dial({ segments, center, caption, size = 180 }: {
  segments: Segment[]; center: string; caption: string; size?: number;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = 70, cx = 90, cy = 90, sweep = 240, start = 150, gap = total > 0 ? 3 : 0;
  const polar = (deg: number) => {
    const a = (deg * Math.PI) / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const arc = (from: number, to: number) => {
    const [x1, y1] = polar(from);
    const [x2, y2] = polar(to);
    return `M ${x1} ${y1} A ${r} ${r} 0 ${to - from > 180 ? 1 : 0} 1 ${x2} ${y2}`;
  };
  let cursor = start;
  const arcs = total > 0
    ? segments.filter((s) => s.value > 0).map((s) => {
        const span = (s.value / total) * sweep;
        const d = arc(cursor + gap / 2, cursor + Math.max(span - gap / 2, gap / 2 + 0.01));
        cursor += span;
        return { d, color: s.color, label: s.label, value: s.value };
      })
    : [];
  return (
    <svg viewBox="0 0 180 150" width={size} height={(size * 150) / 180} role="img"
      aria-label={`${caption}: ${center}. ${segments.map((s) => `${s.label} ${s.value}`).join(", ")}`}>
      <path d={arc(start, start + sweep)} stroke="var(--sunken)" strokeWidth="16" fill="none" strokeLinecap="round" />
      {arcs.map((a) => (
        <path key={a.label} d={a.d} stroke={a.color} strokeWidth="16" fill="none" strokeLinecap="round">
          <title>{`${a.label}: ${a.value}`}</title>
        </path>
      ))}
      <text x="90" y="92" textAnchor="middle" className="fill-ink" style={{ font: "600 34px var(--font-sans)", letterSpacing: "-0.03em" }}>{center}</text>
      <text x="90" y="114" textAnchor="middle" className="fill-muted" style={{ font: "500 9.5px var(--font-mono)", letterSpacing: "0.12em" }}>{caption.toUpperCase()}</text>
    </svg>
  );
}

export function Columns({ values, labels, highlight, height = 96 }: {
  values: number[]; labels: string[]; highlight?: number; height?: number;
}) {
  const max = Math.max(1, ...values);
  const w = 100 / values.length;
  return (
    <div>
      <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" className="w-full" style={{ height }} role="img"
        aria-label={labels.map((l, i) => `${l} ${values[i]}`).join(", ")}>
        {values.map((v, i) => {
          const h = Math.max(2, (v / max) * (height - 6));
          return (
            <rect key={i} x={i * w + w * 0.18} y={height - h} width={w * 0.64} height={h} rx="2.5"
              fill={i === highlight ? "var(--accent)" : "var(--sunken)"}>
              <title>{`${labels[i]}: ${v}`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="flex mt-2">
        {labels.map((l, i) => (
          <span key={l + i} className="text-[10px] font-mono text-faint text-center" style={{ width: `${w}%` }}>{l}</span>
        ))}
      </div>
    </div>
  );
}
