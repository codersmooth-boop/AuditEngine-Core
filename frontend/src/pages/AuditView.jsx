import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getAudit, pdfUrl, boardBriefUrl, streamUrl, auditLogUrl, api } from "../lib/api";
import IntakeZone from "../components/IntakeZone";
import ProcessingPanel from "../components/ProcessingPanel";
import KPIStrip from "../components/KPIStrip";
import FindingsTable from "../components/FindingsTable";
import RoadmapPanel from "../components/RoadmapPanel";
import RescoreSimulator from "../components/RescoreSimulator";
import UtcClock from "../components/UtcClock";
import { useAuth } from "../lib/auth";

async function computeCompositeHash(fileHashes) {
  if (!Array.isArray(fileHashes) || fileHashes.length === 0) return null;
  const concat = fileHashes.map(fh => fh.sha256 || "").join("|");
  const buf = new TextEncoder().encode(concat);
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, "0")).join("");
}

export default function AuditView() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user, logout } = useAuth();
  const [audit, setAudit] = useState(null);
  const [resolved, setResolved] = useState(new Set());
  const [startedAt, setStartedAt] = useState(null);
  const [logs, setLogs] = useState([]);
  const [streamMode, setStreamMode] = useState("sse"); // sse | poll
  const [composite, setComposite] = useState(null);
  const [reinitBusy, setReinitBusy] = useState(false);
  const pollRef = useRef(null);
  const esRef = useRef(null);
  const streamStepRef = useRef(0);

  const load = async () => {
    try {
      const a = await getAudit(id);
      setAudit(a);
      // Hydrate persisted execution log for replay (on completed audits)
      if (Array.isArray(a.stream_logs) && a.stream_logs.length > 0) {
        setLogs(prev => {
          if (prev.length >= a.stream_logs.length) return prev;
          return a.stream_logs.map(l => ({
            type: "log",
            text: l.text,
            tag: l.tag || "OK",
            ts: (l.ts || "").substr(11, 8),
          }));
        });
      }
      if (a.status === "PROCESSING" && !startedAt) setStartedAt(Date.now());
      if (a.status === "COMPLETE" || a.status === "FAILED") {
        clearInterval(pollRef.current);
        if (esRef.current) { esRef.current.close(); esRef.current = null; }
      }
    } catch {
      nav("/dashboard");
    }
  };

  // Open SSE stream when processing; auto-fallback to poll on error.
  useEffect(() => {
    if (!audit || audit.status !== "PROCESSING" || esRef.current) return;
    try {
      const es = new EventSource(streamUrl(audit.audit_id), { withCredentials: true });
      esRef.current = es;
      setStreamMode("sse");
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "log") {
            const ts = new Date().toISOString().substr(11, 8);
            setLogs(prev => [...prev.slice(-300), { ...data, ts }]);
          } else if (data.type === "step") {
            streamStepRef.current = data.step;
            setAudit(a => a ? { ...a, processing_step: data.step } : a);
          } else if (data.type === "done") {
            load();
          }
        } catch { /* ignore */ }
      };
      es.onerror = () => {
        // Fallback: close and rely on polling
        es.close(); esRef.current = null;
        setStreamMode("poll");
      };
    } catch {
      setStreamMode("poll");
    }
  }, [audit?.status, audit?.audit_id]);

  useEffect(() => {
    load();
    pollRef.current = setInterval(load, 1500);
    return () => {
      clearInterval(pollRef.current);
      if (esRef.current) { esRef.current.close(); esRef.current = null; }
    };
  }, [id]);

  // Composite evidence hash — recomputed client-side from ingested file hashes.
  // Matches the value the backend uses internally (see server.py:513).
  // MUST live above any early return to satisfy the Rules of Hooks.
  useEffect(() => {
    if (!audit || audit.status !== "COMPLETE") { setComposite(null); return; }
    computeCompositeHash(audit.file_hashes || []).then(setComposite).catch(() => setComposite(null));
  }, [audit?.status, audit?.file_hashes]);

  if (!audit) {
    return <div className="min-h-screen bg-black text-[#808080] mono text-xs p-8 ae-cursor">LOADING AUDIT</div>;
  }

  const reinitiate = async () => {
    if (reinitBusy) return;
    setReinitBusy(true);
    try {
      await api.post(`/audits/${audit.audit_id}/reset`);
      await load();
    } catch (e) {
      // Fallback: force a reload so the user is not stuck.
      window.location.reload();
    } finally {
      setReinitBusy(false);
    }
  };

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
          <ProcessingPanel step={audit.processing_step || 1} startedAt={startedAt || Date.now()} logs={logs} streamMode={streamMode} />
        </>
      )}

      {audit.status === "FAILED" && (
        <div className="p-8">
          <div className="ae-border-strong p-8 bg-[#050505]">
            <div className="mono text-[10px] tracking-widest text-[#FF0000]">// FAILED</div>
            <div className="sans text-xl mt-2">Processing terminated. Evidence set retained; re-initiate to reprocess.</div>
            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={reinitiate}
                disabled={reinitBusy}
                data-testid="reinitiate-btn"
                className="mono text-xs tracking-[0.2em] ae-border-strong px-6 py-3 bg-[#00FF41] text-black hover:bg-white disabled:bg-[#333] disabled:text-[#808080] transition-colors"
              >
                {reinitBusy ? "RESETTING…" : "▸ RE-INITIATE"}
              </button>
              <button
                type="button"
                onClick={() => nav("/dashboard")}
                className="mono text-xs tracking-[0.2em] px-6 py-3 border-[0.5px] border-[#2A2A2A] text-[#808080] hover:text-white hover:border-white transition-colors"
              >← WORKSPACE</button>
            </div>
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

              <div className="ae-border-strong p-6" data-testid="audit-provenance">
                <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// PROVENANCE</div>
                <div className="sans text-xl font-light mt-2">Composite evidence hash.</div>
                <div className="mono text-[11px] text-[#E8E8E8] break-all mt-4 leading-relaxed" data-testid="composite-hash">
                  {composite || "— computing —"}
                </div>
                <div className="mono text-[10px] text-[#808080] mt-3 leading-relaxed">
                  SHA-256 of ({(audit.file_hashes || []).length}) ingested file hashes, pipe-joined in insertion order.
                </div>
                {composite && (
                  <button
                    type="button"
                    onClick={() => nav(`/verify?root=${composite}`)}
                    data-testid="verify-provenance-btn"
                    className="mono text-[10px] tracking-widest text-[#00FF41] mt-4 hover:text-white"
                  >→ VERIFY ROOT</button>
                )}
              </div>

              <div className="ae-border-strong p-6">
                <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// PDF DELIVERY</div>
                <div className="sans text-xl font-light mt-2">Signed audit report ready.</div>
                <div className="mt-4 flex flex-col gap-3">
                  <a
                    href={pdfUrl(audit.audit_id)}
                    target="_blank" rel="noreferrer"
                    data-testid="download-pdf-btn"
                    className="mono text-xs tracking-[0.2em] ae-border-strong px-6 py-3 bg-[#00FF41] text-black hover:bg-white transition-colors text-center"
                  >↓ DOWNLOAD FULL REPORT (PDF)</a>
                  <a
                    href={boardBriefUrl(audit.audit_id)}
                    target="_blank" rel="noreferrer"
                    data-testid="board-brief-btn"
                    className="mono text-xs tracking-[0.2em] ae-border-strong px-6 py-3 bg-black text-[#E8E8E8] hover:bg-[#0D0D0D] hover:text-white transition-colors text-center"
                  >⧉ GENERATE BOARD BRIEF (1-PAGE)</a>
                  <a
                    href={auditLogUrl(audit.audit_id)}
                    target="_blank" rel="noreferrer"
                    data-testid="audit-log-btn"
                    className="mono text-xs tracking-[0.2em] ae-border-strong px-6 py-3 bg-black text-[#E8E8E8] hover:bg-[#0D0D0D] hover:text-white transition-colors text-center"
                  >⧉ EXPORT SIGNED AUDIT LOG (.LOG)</a>
                  <div className="mono text-[10px] text-[#808080] leading-relaxed">
                    Full report: Board Brief cover + findings + technical appendix.<br/>
                    Signed .LOG: regulator-defensible execution trail with SHA-256 evidence fingerprint.
                  </div>
                </div>
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
