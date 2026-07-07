import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getAudit, pdfUrl } from "../lib/api";
import IntakeZone from "../components/IntakeZone";
import ProcessingPanel from "../components/ProcessingPanel";
import KPIStrip from "../components/KPIStrip";
import FindingsTable from "../components/FindingsTable";
import RoadmapPanel from "../components/RoadmapPanel";
import RescoreSimulator from "../components/RescoreSimulator";
import UtcClock from "../components/UtcClock";
import { useAuth } from "../lib/auth";

export default function AuditView() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const [audit, setAudit] = useState(null);
  const [resolved, setResolved] = useState(new Set());
  const [startedAt, setStartedAt] = useState(null);
  const pollRef = useRef(null);

  const load = async () => {
    try {
      const a = await getAudit(id);
      setAudit(a);
      if (a.status === "PROCESSING" && !startedAt) setStartedAt(Date.now());
      if (a.status === "COMPLETE" || a.status === "FAILED") {
        clearInterval(pollRef.current);
      }
    } catch {
      nav("/dashboard");
    }
  };

  useEffect(() => {
    load();
    pollRef.current = setInterval(load, 1200);
    return () => clearInterval(pollRef.current);
  }, [id]);

  if (!audit) {
    return <div className="min-h-screen bg-black text-[#808080] mono text-xs p-8 ae-cursor">LOADING AUDIT</div>;
  }

  const toggleResolve = (fid) => {
    setResolved(prev => {
      const n = new Set(prev);
      if (n.has(fid)) n.delete(fid); else n.add(fid);
      return n;
    });
  };

  const totalImpact = (audit.findings || [])
    .filter(f => resolved.has(f.id))
    .reduce((s, f) => s + (f.impact_score || 0), 0);
  const projected = Math.min(100, (audit.compliance_score || 0) + totalImpact);
  const showSimulated = resolved.size > 0;

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8]">
      <header className="ae-border-strong border-b flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-6">
          <button onClick={() => nav("/dashboard")} className="mono text-[10px] text-[#808080] hover:text-white">← WORKSPACE</button>
          <div className="mono text-xs tracking-[0.2em]">AUDITENGINE</div>
        </div>
        <div className="flex items-center gap-6">
          <UtcClock />
          <div className="mono text-[10px] text-[#808080]">{user?.email}</div>
          <button onClick={logout} className="mono text-[10px] text-[#808080] hover:text-[#FF0000]">LOGOUT</button>
        </div>
      </header>

      {/* Case bar */}
      <div className="ae-border-strong border-b px-8 py-6 grid grid-cols-4 items-center">
        <div className="col-span-2">
          <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// CASE {audit.audit_id.toUpperCase()}</div>
          <h1 className="sans text-3xl font-light mt-2" data-testid="audit-client-name">{audit.client_name}</h1>
        </div>
        <div>
          <div className="mono text-[10px] text-[#808080] tracking-widest">NACE REV. 2</div>
          <div className="mono text-sm text-[#E8E8E8] mt-1">{audit.nace_code}</div>
          <div className="sans text-xs text-[#808080] mt-1 truncate">{audit.nace_name}</div>
        </div>
        <div className="text-right">
          <div className="mono text-[10px] text-[#808080] tracking-widest">REPORTING YEAR</div>
          <div className="mono text-3xl mt-1">{audit.reporting_year}</div>
        </div>
      </div>

      {/* Intake or processing or reveal */}
      {audit.status === "DRAFT" && (
        <div className="p-8">
          <IntakeZone auditId={audit.audit_id} onUploaded={load} />
        </div>
      )}

      {audit.status === "PROCESSING" && (
        <>
          <div className="p-8">
            <div data-testid="intake-status-bar" className="ae-border-strong h-8 flex items-center px-4 bg-black">
              <span className="w-2 h-2 bg-[#00FF41] ae-pulse mr-3" />
              <span className="mono text-[10px] tracking-[0.3em] text-[#E8E8E8]">RECEIVING INPUT</span>
              <span className="mono text-[10px] text-[#808080] ml-6 truncate">{(audit.files || []).join(" · ")}</span>
            </div>
          </div>
          <ProcessingPanel step={audit.processing_step || 1} startedAt={startedAt || Date.now()} />
        </>
      )}

      {audit.status === "FAILED" && (
        <div className="p-8">
          <div className="ae-border-strong p-8 bg-[#050505]">
            <div className="mono text-[10px] tracking-widest text-[#FF0000]">// FAILED</div>
            <div className="sans text-xl mt-2">Processing failed. Try re-uploading.</div>
          </div>
        </div>
      )}

      {audit.status === "COMPLETE" && (
        <div className="ae-fade-in" data-testid="reveal-panel">
          <KPIStrip audit={audit} simulatedScore={showSimulated ? projected : null} />

          <div className="grid grid-cols-3 gap-0">
            <div className="col-span-2 border-r-[0.5px] border-[#2A2A2A]">
              {audit.executive_summary && (
                <div className="p-8 border-b-[0.5px] border-[#2A2A2A]">
                  <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// EXECUTIVE SUMMARY</div>
                  <p className="sans text-lg leading-relaxed text-[#E8E8E8] mt-3 max-w-3xl" data-testid="executive-summary">{audit.executive_summary}</p>
                </div>
              )}
              <div className="p-8">
                <FindingsTable
                  findings={audit.findings || []}
                  resolved={resolved}
                  onToggleResolve={toggleResolve}
                />
              </div>
              <div className="p-8 border-t-[0.5px] border-[#2A2A2A]">
                <RoadmapPanel roadmap={audit.roadmap || []} />
              </div>
            </div>
            <aside className="p-8 space-y-8">
              <RescoreSimulator audit={audit} resolved={resolved} projectedScore={projected} />

              <div className="ae-border-strong p-6">
                <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// PDF DELIVERY</div>
                <div className="sans text-xl font-light mt-2">Signed audit report ready.</div>
                <a
                  href={pdfUrl(audit.audit_id)}
                  target="_blank" rel="noreferrer"
                  data-testid="download-pdf-btn"
                  className="mt-4 inline-block mono text-xs tracking-[0.2em] ae-border-strong px-6 py-3 bg-[#00FF41] text-black hover:bg-white transition-colors"
                >↓ DOWNLOAD REPORT (PDF)</a>
              </div>

              <div className="ae-border-strong">
                <div className="mono text-[10px] tracking-[0.3em] text-[#808080] px-4 py-3 border-b-[0.5px] border-[#1A1A1A]">// INTAKE BUCKETS</div>
                <BucketRow label="OPERATIONAL ENERGY" findings={audit.findings} bucket="OPERATIONAL_ENERGY" />
                <BucketRow label="SUPPLY CHAIN" findings={audit.findings} bucket="SUPPLY_CHAIN" />
                <BucketRow label="HUMAN / SOCIAL CAPITAL" findings={audit.findings} bucket="HUMAN_SOCIAL_CAPITAL" />
                <BucketRow label="CONTEXT LAYER" findings={audit.findings} bucket="CONTEXT_LAYER" last />
              </div>
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}

function BucketRow({ label, findings, bucket, last }) {
  const items = (findings || []).filter(f => f.bucket === bucket);
  const missing = items.filter(f => f.status === "MISSING").length;
  const noncomp = items.filter(f => f.status === "NON_COMPLIANT").length;
  return (
    <div className={`px-4 py-3 grid grid-cols-4 gap-2 items-center ${last ? "" : "border-b-[0.5px] border-[#1A1A1A]"}`}>
      <div className="col-span-2 mono text-[10px] text-[#E8E8E8] tracking-widest">{label}</div>
      <div className="mono text-[10px] text-[#FFBF00] text-right">{missing} MISSING</div>
      <div className="mono text-[10px] text-[#FF0000] text-right">{noncomp} FAIL</div>
    </div>
  );
}
