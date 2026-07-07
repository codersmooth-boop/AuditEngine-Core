import React from "react";
import ComplianceRing from "./ComplianceRing";

const fmtEUR = (n) => new Intl.NumberFormat("en-EU", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n || 0);

export default function KPIStrip({ audit, simulatedScore }) {
  const shownScore = simulatedScore ?? audit.compliance_score ?? 0;
  const gw = audit.greenwashing_risk || "NONE";
  const gwColor = { HIGH: "#FF0000", MODERATE: "#FFBF00", LOW: "#00FF41", NONE: "#808080" }[gw];

  return (
    <div className="ae-border-strong border-y grid grid-cols-4 items-stretch" data-testid="kpi-strip">
      <div className="p-8 flex items-center gap-8 border-r-[0.5px] border-[#2A2A2A]">
        <ComplianceRing score={shownScore} size={140} animate={simulatedScore == null} />
        <div>
          <div className="mono text-[10px] text-[#808080] tracking-widest">COMPLIANCE</div>
          <div className="sans text-sm text-[#E8E8E8] mt-1">
            {shownScore >= 80 ? "Materially compliant" : shownScore >= 60 ? "Partial alignment" : "Non-compliant posture"}
          </div>
          {simulatedScore != null && (
            <div className="mono text-[10px] text-[#00FF41] mt-1">// PROJECTED</div>
          )}
        </div>
      </div>

      <KPI label="TOTAL VALUE AT STAKE" value={fmtEUR(audit.value_at_stake_eur)} testid="kpi-value-at-stake" />
      <KPI label="CRITICAL FINDINGS" value={audit.critical_findings_count ?? 0} tone="#FF0000" testid="kpi-critical-findings" />
      <KPI label="GREENWASHING RISK" value={gw} tone={gwColor} testid="kpi-greenwashing" />
    </div>
  );
}

function KPI({ label, value, tone = "#E8E8E8", testid }) {
  return (
    <div className="p-8 border-r-[0.5px] border-[#2A2A2A] last:border-r-0" data-testid={testid}>
      <div className="mono text-[10px] text-[#808080] tracking-widest">{label}</div>
      <div className="mono text-4xl mt-4" style={{ color: tone }}>{value}</div>
    </div>
  );
}
