import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listAudits, snapshotUrl } from "../lib/api";
import { useAuth } from "../lib/auth";
import UtcClock from "../components/UtcClock";
import VerifierModal from "../components/VerifierModal";

// SHA-256 helper for composite fingerprint (browser-side, deterministic)
async function composite(hashes) {
  if (!hashes || hashes.length === 0) return "—";
  const joined = hashes.map(h => h.sha256 || "").join("|");
  const buf = new TextEncoder().encode(joined);
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, "0")).join("");
}

const RISK_COLOR = { HIGH: "#FF0000", MODERATE: "#FFBF00", LOW: "#00FF41", NONE: "#808080" };

export default function Ledger() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [audits, setAudits] = useState([]);
  const [q, setQ] = useState("");
  const [hashes, setHashes] = useState({});
  const [fullHashes, setFullHashes] = useState({});
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(null);
  const currentYear = new Date().getUTCFullYear();
  const [year, setYear] = useState(currentYear - 1);

  useEffect(() => {
    (async () => {
      try {
        const list = await listAudits();
        setAudits(list);
        const map = {};
        const full = {};
        for (const a of list) {
          const h = await composite(a.file_hashes || []);
          full[a.audit_id] = h;
          map[a.audit_id] = h === "—" ? "—" : h.slice(0, 16);
        }
        setHashes(map);
        setFullHashes(full);
      } finally { setLoading(false); }
    })();
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return audits;
    return audits.filter(a =>
      (a.client_name || "").toLowerCase().includes(s) ||
      (a.audit_id || "").toLowerCase().includes(s) ||
      (a.nace_name || "").toLowerCase().includes(s) ||
      String(a.reporting_year || "").includes(s) ||
      (hashes[a.audit_id] || "").includes(s)
    );
  }, [q, audits, hashes]);

  const scoreColor = (s) => s == null ? "#808080" : s >= 80 ? "#00FF41" : s >= 60 ? "#FFBF00" : "#FF0000";

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8]">
      <header className="ae-border-strong border-b flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-8">
          <div className="mono text-xs tracking-[0.2em]">AUDITENGINE</div>
          <div className="flex gap-6">
            <button onClick={() => nav("/dashboard")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white">// WORKSPACE</button>
            <span className="mono text-[10px] tracking-widest text-[#00FF41]">// COMPLIANCE LEDGER</span>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <UtcClock />
          <div className="mono text-[10px] text-[#808080]">{user?.email}</div>
          <button onClick={logout} className="mono text-[10px] text-[#808080] hover:text-[#FF0000]">LOGOUT</button>
        </div>
      </header>

      <div className="ae-border-strong border-b px-8 py-10 flex items-end justify-between gap-6">
        <div>
          <div className="mono text-[10px] text-[#808080] tracking-widest mb-3">// SYSTEM OF RECORD</div>
          <h1 className="sans text-5xl font-light tracking-tight">Compliance Ledger.</h1>
          <p className="mono text-xs text-[#808080] mt-3">{filtered.length} of {audits.length} audits · verified evidence chain per row</p>
        </div>
        <div className="flex items-end gap-3">
          <div>
            <div className="mono text-[10px] text-[#808080] tracking-widest mb-2">FY</div>
            <select
              data-testid="snapshot-year"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="bg-[#050505] ae-border-strong px-3 py-3 mono text-xs text-[#E8E8E8] focus:outline-none focus:border-[#00FF41]"
            >
              {Array.from({ length: 8 }, (_, i) => currentYear - i).map(y =>
                <option key={y} value={y}>{y}</option>
              )}
            </select>
          </div>
          <a
            data-testid="snapshot-btn"
            href={snapshotUrl(year)}
            target="_blank" rel="noreferrer"
            className="mono text-xs tracking-[0.2em] ae-border-strong px-6 py-3 bg-[#00FF41] text-black hover:bg-white transition-colors"
          >⧉ GENERATE YEARLY SNAPSHOT</a>
          <input
            data-testid="ledger-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search client · NACE · hash · year"
            className="bg-[#050505] ae-border-strong px-4 py-3 mono text-xs text-[#E8E8E8] w-72 focus:outline-none focus:border-[#00FF41]"
          />
        </div>
      </div>

      <div className="px-8">
        <div className="grid grid-cols-12 mono text-[10px] tracking-widest text-[#808080] py-3 border-b-[0.5px] border-[#2A2A2A]">
          <div className="col-span-2">AUDIT ID</div>
          <div className="col-span-3">CLIENT / ENTITY</div>
          <div className="col-span-2">DATE</div>
          <div className="col-span-1">SCORE</div>
          <div className="col-span-1">RISK</div>
          <div className="col-span-2">EVIDENCE HASH</div>
          <div className="col-span-1 text-right">VERIFY</div>
        </div>

        {loading && <div className="mono text-xs text-[#808080] py-8 ae-cursor">LOADING LEDGER</div>}

        {!loading && filtered.length === 0 && (
          <div className="mono text-xs text-[#808080] py-16 text-center">NO ENTRIES</div>
        )}

        {filtered.map((a) => (
          <div
            key={a.audit_id}
            data-testid={`ledger-row-${a.audit_id}`}
            onClick={() => nav(`/audits/${a.audit_id}`)}
            className="grid grid-cols-12 mono text-xs items-center py-4 border-b-[0.5px] border-[#1A1A1A] hover:bg-[#0D0D0D] cursor-pointer transition-colors"
          >
            <div className="col-span-2 text-[#808080] truncate">{a.audit_id}</div>
            <div className="col-span-3 sans text-sm text-[#E8E8E8] truncate pr-4">
              {a.client_name}
              <div className="mono text-[10px] text-[#808080] truncate">{a.nace_code} · {a.nace_name}</div>
            </div>
            <div className="col-span-2 text-[#808080]">{(a.created_at || "").substr(0, 10)} · FY{a.reporting_year}</div>
            <div className="col-span-1" style={{ color: scoreColor(a.compliance_score) }}>{a.compliance_score ?? "—"}</div>
            <div className="col-span-1" style={{ color: RISK_COLOR[a.greenwashing_risk] || "#808080" }}>{a.greenwashing_risk || "—"}</div>
            <div className="col-span-2 text-[#00FF41] truncate">{hashes[a.audit_id] || "—"}...</div>
            <div className="col-span-1 text-right">
              <button
                data-testid={`verify-btn-${a.audit_id}`}
                onClick={(e) => { e.stopPropagation(); setVerifying(a); }}
                className="mono text-[10px] tracking-widest text-[#808080] hover:text-[#00FF41]"
              >VERIFY →</button>
            </div>
          </div>
        ))}
      </div>

      {verifying && (
        <VerifierModal
          audit={verifying}
          expectedHash={fullHashes[verifying.audit_id]}
          onClose={() => setVerifying(null)}
        />
      )}
    </div>
  );
}
