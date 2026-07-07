import React from "react";

const fmt = (n) => new Intl.NumberFormat("en-EU").format(Math.round(n || 0));

export default function RoadmapPanel({ roadmap }) {
  return (
    <div className="ae-border-strong" data-testid="roadmap-panel">
      <div className="px-6 py-4 border-b-[0.5px] border-[#2A2A2A]">
        <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// STRATEGIC VALUE ROADMAP · TOP 5</div>
        <h3 className="sans text-2xl font-light mt-2">Action → Metric → € Saving</h3>
      </div>
      {roadmap.map((r, i) => (
        <div key={r.id || i} className="grid grid-cols-12 gap-6 px-6 py-5 border-b-[0.5px] border-[#1A1A1A] last:border-b-0" data-testid={`roadmap-item-${i}`}>
          <div className="col-span-1 mono text-[#808080] text-2xl">{String(i + 1).padStart(2, "0")}</div>
          <div className="col-span-5">
            <div className="mono text-[10px] text-[#808080] tracking-widest">ACTION</div>
            <div className="sans text-sm text-[#E8E8E8] mt-1">{r.action}</div>
            <div className="mono text-[10px] text-[#808080] mt-3">→ {r.metric_impact}</div>
          </div>
          <div className="col-span-2">
            <div className="mono text-[10px] text-[#808080] tracking-widest">€ SAVING</div>
            <div className="mono text-lg text-[#00FF41] mt-1">€{fmt(r.saving_eur)}</div>
          </div>
          <div className="col-span-2">
            <div className="mono text-[10px] text-[#808080] tracking-widest">COST</div>
            <div className="mono text-lg text-[#E8E8E8] mt-1">€{fmt(r.implementation_cost_eur)}</div>
          </div>
          <div className="col-span-2">
            <div className="mono text-[10px] text-[#808080] tracking-widest">PAYBACK</div>
            <div className="mono text-lg text-[#FFBF00] mt-1">{r.payback_months} mo</div>
          </div>
        </div>
      ))}
    </div>
  );
}
