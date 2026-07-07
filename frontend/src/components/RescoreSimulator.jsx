import React, { useMemo } from "react";

export default function RescoreSimulator({ audit, resolved, projectedScore }) {
  const totalImpact = useMemo(() => {
    return (audit.findings || [])
      .filter(f => resolved.has(f.id))
      .reduce((s, f) => s + (f.impact_score || 0), 0);
  }, [audit.findings, resolved]);

  const base = audit.compliance_score ?? 0;
  const projected = projectedScore ?? Math.min(100, base + totalImpact);

  return (
    <div className="ae-border-strong p-6" data-testid="rescore-simulator">
      <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// RE-SCORE SIMULATOR</div>
      <h3 className="sans text-2xl font-light mt-2">Projected compliance posture.</h3>
      <div className="grid grid-cols-3 gap-4 mt-6">
        <Cell label="CURRENT" value={base} tone={color(base)} testid="sim-current" />
        <Cell label="Δ IMPACT" value={`+${totalImpact}`} tone="#00FF41" testid="sim-delta" />
        <Cell label="PROJECTED" value={projected} tone={color(projected)} testid="sim-projected" />
      </div>
      <div className="mono text-[10px] text-[#808080] mt-6">
        Tick findings in the table to project a new compliance score. Resolves compound linearly by declared impact.
      </div>
    </div>
  );
}

const color = (s) => s >= 80 ? "#00FF41" : s >= 60 ? "#FFBF00" : "#FF0000";

function Cell({ label, value, tone, testid }) {
  return (
    <div className="ae-border p-4" data-testid={testid}>
      <div className="mono text-[10px] text-[#808080] tracking-widest">{label}</div>
      <div className="mono text-4xl mt-2" style={{ color: tone }}>{value}</div>
    </div>
  );
}
