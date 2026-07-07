import React, { useMemo, useState } from "react";

const SEV_STYLE = {
  CRITICAL: "text-[#FF0000] border-[#FF0000]",
  MODERATE: "text-[#FFBF00] border-[#FFBF00]",
  COMPLIANT: "text-[#00FF41] border-[#00FF41]",
};

const STATUS_STYLE = {
  COMPLIANT: "text-[#00FF41]",
  NON_COMPLIANT: "text-[#FF0000]",
  MISSING: "text-[#FFBF00]",
};

const BUCKET_LABEL = {
  OPERATIONAL_ENERGY: "OPS ENERGY",
  SUPPLY_CHAIN: "SUPPLY CHAIN",
  HUMAN_SOCIAL_CAPITAL: "HUMAN/SOCIAL",
  CONTEXT_LAYER: "CONTEXT",
};

export default function FindingsTable({ findings, resolved, onToggleResolve }) {
  const [openId, setOpenId] = useState(null);
  const [filter, setFilter] = useState("ALL");

  const sorted = useMemo(() => {
    const order = { CRITICAL: 0, MODERATE: 1, COMPLIANT: 2 };
    return [...findings]
      .filter(f => filter === "ALL" || f.severity === filter)
      .sort((a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9));
  }, [findings, filter]);

  return (
    <div className="ae-border-strong" data-testid="findings-table">
      <div className="flex items-center justify-between px-6 py-4 border-b-[0.5px] border-[#2A2A2A]">
        <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// FINDINGS · {findings.length} TOTAL</div>
        <div className="flex gap-0 ae-border">
          {["ALL", "CRITICAL", "MODERATE", "COMPLIANT"].map((k) => (
            <button
              key={k}
              data-testid={`findings-filter-${k.toLowerCase()}`}
              onClick={() => setFilter(k)}
              className={`mono text-[10px] tracking-widest px-4 py-2 border-r-[0.5px] border-[#1A1A1A] last:border-r-0 ${filter === k ? "bg-[#0D0D0D] text-[#00FF41]" : "text-[#808080] hover:text-[#E8E8E8]"}`}
            >{k}</button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-12 mono text-[10px] tracking-widest text-[#808080] px-6 py-3 border-b-[0.5px] border-[#1A1A1A]">
        <div className="col-span-1">SEV</div>
        <div className="col-span-4">DATA POINT</div>
        <div className="col-span-2">STATUS</div>
        <div className="col-span-2">REG. REF</div>
        <div className="col-span-2">BUCKET</div>
        <div className="col-span-1 text-right">RESOLVE</div>
      </div>

      {sorted.map((f) => {
        const open = openId === f.id;
        const isResolved = resolved?.has(f.id);
        return (
          <div key={f.id} className="border-b-[0.5px] border-[#1A1A1A]">
            <div
              data-testid={`finding-row-${f.id}`}
              onClick={() => setOpenId(open ? null : f.id)}
              className="grid grid-cols-12 items-center px-6 py-4 hover:bg-[#0D0D0D] cursor-pointer"
            >
              <div className="col-span-1">
                <span className={`mono text-[10px] px-2 py-0.5 border-[0.5px] tracking-widest ${SEV_STYLE[f.severity]}`}>
                  {f.severity}
                </span>
              </div>
              <div className="col-span-4 sans text-sm text-[#E8E8E8]">{f.data_point}</div>
              <div className={`col-span-2 mono text-xs ${STATUS_STYLE[f.status] || "text-[#808080]"}`}>{f.status}</div>
              <div className="col-span-2 mono text-xs text-[#808080]">{f.regulatory_ref}</div>
              <div className="col-span-2 mono text-[10px] text-[#808080]">{BUCKET_LABEL[f.bucket] || f.bucket}</div>
              <div className="col-span-1 text-right">
                <label className="inline-flex items-center cursor-pointer" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    data-testid={`resolve-${f.id}`}
                    checked={!!isResolved}
                    onChange={() => onToggleResolve?.(f.id)}
                    disabled={f.severity === "COMPLIANT"}
                    className="accent-[#00FF41] w-3 h-3"
                  />
                </label>
              </div>
            </div>
            {open && (
              <div className="px-6 pb-6 bg-[#050505] ae-fade-in" data-testid={`finding-detail-${f.id}`}>
                <div className="grid grid-cols-3 gap-8 pt-4 border-t-[0.5px] border-[#1A1A1A]">
                  <div className="col-span-2">
                    <div className="mono text-[10px] text-[#808080] tracking-widest mb-2">// FINDING</div>
                    <p className="sans text-sm text-[#E8E8E8] leading-relaxed">{f.finding_detail}</p>
                    {f.recommendation && (
                      <>
                        <div className="mono text-[10px] text-[#808080] tracking-widest mt-6 mb-2">// RECOMMENDATION</div>
                        <p className="sans text-sm text-[#E8E8E8] leading-relaxed">→ {f.recommendation}</p>
                      </>
                    )}
                  </div>
                  <div>
                    <div className="mono text-[10px] text-[#808080] tracking-widest mb-2">// IMPACT SCORE</div>
                    <div className="mono text-3xl text-[#00FF41]">+{f.impact_score ?? 0}</div>
                    <div className="mono text-[10px] text-[#808080] mt-1">POINTS IF RESOLVED</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
