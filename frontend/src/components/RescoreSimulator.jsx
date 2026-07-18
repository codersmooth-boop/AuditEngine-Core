import React, { useMemo, useState, useEffect } from "react";

const fmtEur = (n) => `€${Math.round(n).toLocaleString("en-US")}`;
const color = (s) => s >= 80 ? "#00FF41" : s >= 60 ? "#FFBF00" : "#FF0000";

export default function RescoreSimulator({ audit, resolved, projectedScore }) {
  const totalImpact = useMemo(() => {
    return (audit.findings || [])
      .filter(f => resolved.has(f.id))
      .reduce((s, f) => s + (f.impact_score || 0), 0);
  }, [audit.findings, resolved]);

  const deltaEur = useMemo(() => {
    return (audit.findings || [])
      .filter(f => resolved.has(f.id))
      .reduce((s, f) => s + (f.value_at_stake_eur || f.euro_impact || 0), 0);
  }, [audit.findings, resolved]);

  const base = audit.compliance_score ?? 0;
  const projected = projectedScore ?? Math.min(100, base + totalImpact);

  // LOCK SCENARIO — snapshot the current resolved set for later comparison.
  // Persisted per audit in localStorage so a workspace can iterate over sessions.
  const storageKey = `ae:scenario:${audit.audit_id}`;
  const [locked, setLocked] = useState(null);
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) setLocked(JSON.parse(raw));
    } catch { /* ignore */ }
  }, [storageKey]);

  const lockNow = () => {
    const snap = {
      scenario_name: `SCENARIO ${new Date().toISOString().slice(0, 19).replace("T", " · ")}Z`,
      base_score: base,
      projected_score: projected,
      delta_score: totalImpact,
      delta_eur: deltaEur,
      resolved_ids: Array.from(resolved),
      locked_at: new Date().toISOString(),
    };
    window.localStorage.setItem(storageKey, JSON.stringify(snap));
    setLocked(snap);
  };
  const clearLocked = () => {
    window.localStorage.removeItem(storageKey);
    setLocked(null);
  };

  const scenarioName = locked ? locked.scenario_name : "SCENARIO · [DRAFT]";
  const drift = locked ? projected - locked.projected_score : null;

  return (
    <div className="ae-border-strong" data-testid="rescore-simulator">
      {/* Header bar with scenario name + lock control */}
      <div className="ae-border-strong border-b px-6 py-3 flex items-center justify-between">
        <div>
          <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// RE-SCORE SIMULATOR</div>
          <div className="mono text-[11px] tracking-widest mt-1"
               style={{ color: locked ? "#FFD700" : "#E8E8E8" }}
               data-testid="scenario-name">
            {scenarioName}
          </div>
        </div>
        {locked ? (
          <button
            type="button"
            onClick={clearLocked}
            data-testid="scenario-clear-btn"
            className="mono text-[10px] tracking-widest px-3 py-2 border-[0.5px] border-[#2A2A2A] text-[#808080] hover:text-[#FF0000] hover:border-[#FF0000]"
          >× UNLOCK</button>
        ) : (
          <button
            type="button"
            onClick={lockNow}
            data-testid="scenario-lock-btn"
            disabled={resolved.size === 0}
            className="mono text-[10px] tracking-widest px-3 py-2 border-[0.5px] border-[#FFD700] text-[#FFD700] hover:bg-[#FFD700] hover:text-black disabled:border-[#333] disabled:text-[#333] disabled:cursor-not-allowed"
          >▸ LOCK SCENARIO</button>
        )}
      </div>

      <div className="p-6">
        <h3 className="sans text-2xl font-light">Projected compliance posture.</h3>

        {/* Four-cell what-if grid — CURRENT · Δ SCORE · PROJECTED · Δ € SAVED */}
        <div className="grid grid-cols-2 gap-0 ae-border-strong mt-6">
          <Cell label="CURRENT"    value={base}                tone={color(base)}      testid="sim-current" />
          <Cell label="Δ SCORE"    value={`+${totalImpact}`}   tone="#00FF41"          testid="sim-delta"     border />
          <Cell label="PROJECTED"  value={projected}           tone={color(projected)} testid="sim-projected" borderTop />
          <Cell label="Δ € SAVED"  value={fmtEur(deltaEur)}    tone="#FFD700"          testid="sim-eur"       border borderTop />
        </div>

        {/* Drift row (only when a scenario is locked) */}
        {locked && drift !== null && (
          <div className="ae-border-strong mt-4 grid grid-cols-[140px_1fr] gap-0" data-testid="scenario-drift">
            <div className="mono text-[10px] tracking-widest text-[#808080] px-4 py-3 border-r-[0.5px] border-[#2A2A2A] flex items-center">DRIFT vs LOCKED</div>
            <div className="mono text-sm px-4 py-3" style={{ color: drift === 0 ? "#808080" : drift > 0 ? "#00FF41" : "#FF0000" }}>
              {drift > 0 ? "+" : ""}{drift} · locked at score {locked.projected_score} on {locked.locked_at.slice(0, 10)}
            </div>
          </div>
        )}

        <div className="mono text-[10px] text-[#808080] mt-6 leading-relaxed">
          Tick findings in the table to compound their declared impact. LOCK SCENARIO to
          snapshot a what-if for board review; DRIFT tracks divergence from the locked baseline.
        </div>
      </div>
    </div>
  );
}

function Cell({ label, value, tone, testid, border = false, borderTop = false }) {
  const cls = [
    "p-4",
    border    ? "border-l-[0.5px] border-[#2A2A2A]" : "",
    borderTop ? "border-t-[0.5px] border-[#2A2A2A]" : "",
  ].join(" ");
  return (
    <div className={cls} data-testid={testid}>
      <div className="mono text-[10px] text-[#808080] tracking-widest">{label}</div>
      <div className="mono text-3xl mt-2" style={{ color: tone }}>{value}</div>
    </div>
  );
}
