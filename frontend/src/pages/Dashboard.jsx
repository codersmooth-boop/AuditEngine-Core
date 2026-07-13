import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { listAudits, deleteAudit, setLeaderboardOptIn } from "../lib/api";
import NewAuditDrawer from "../components/NewAuditDrawer";
import UtcClock from "../components/UtcClock";

export default function Dashboard() {
  const { user, logout, refresh } = useAuth();
  const [audits, setAudits] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [optSaving, setOptSaving] = useState(false);
  const nav = useNavigate();

  const load = async () => {
    setLoading(true);
    try { setAudits(await listAudits()); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const toggleOptIn = async () => {
    if (optSaving) return;
    setOptSaving(true);
    try {
      await setLeaderboardOptIn(!user?.leaderboard_opt_in);
      await refresh();
    } finally { setOptSaving(false); }
  };

  const onCreated = (a) => {
    setOpen(false);
    nav(`/audits/${a.audit_id}`);
  };

  const remove = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this audit?")) return;
    await deleteAudit(id);
    load();
  };

  const statusColor = {
    COMPLETE: "text-[#00FF41]",
    PROCESSING: "text-[#FFBF00]",
    FAILED: "text-[#FF0000]",
    DRAFT: "text-[#808080]",
  };

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8]">
      <header className="ae-border-strong border-b flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-8">
          <div className="mono text-xs tracking-[0.2em]">AUDITENGINE</div>
          <div className="flex gap-6">
            <span className="mono text-[10px] tracking-widest text-[#00FF41]">// WORKSPACE</span>
            <button data-testid="nav-ledger" onClick={() => nav("/ledger")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white">⧉ COMPLIANCE LEDGER</button>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <UtcClock />
          <div className="mono text-[10px] text-[#808080]" data-testid="user-email">{user?.email}</div>
          <button data-testid="logout-btn" onClick={logout} className="mono text-[10px] text-[#808080] hover:text-[#FF0000]">LOGOUT</button>
        </div>
      </header>

      <div className="ae-border-strong border-b flex items-center justify-between px-8 py-10">
        <div>
          <div className="mono text-[10px] text-[#808080] tracking-widest mb-3">// COMMAND</div>
          <h1 className="sans text-5xl font-light tracking-tight">Audit Workspace.</h1>
          <p className="mono text-xs text-[#808080] mt-3">{audits.length} audit{audits.length === 1 ? "" : "s"} on record</p>
        </div>
        <div className="flex items-center gap-4">
          <button
            data-testid="leaderboard-opt-in-toggle"
            onClick={toggleOptIn}
            disabled={optSaving}
            className={`ae-border-strong px-5 py-4 flex items-center gap-3 ${user?.leaderboard_opt_in ? "bg-black text-[#00FF41]" : "bg-black text-[#808080] hover:text-white"}`}
          >
            <span className={`w-3 h-3 inline-block ${user?.leaderboard_opt_in ? "bg-[#00FF41]" : "ae-border-strong"}`} />
            <span className="mono text-[10px] tracking-widest">
              {user?.leaderboard_opt_in ? "LEADERBOARD · LISTED" : "LEADERBOARD · PRIVATE"}
            </span>
          </button>
          <button
            data-testid="new-audit-btn"
            onClick={() => setOpen(true)}
            className="mono text-xs tracking-[0.2em] ae-border-strong px-8 py-4 bg-[#00FF41] text-black hover:bg-white transition-colors"
          >
            + NEW AUDIT
          </button>
        </div>
      </div>

      <div className="px-8 py-6">
        <div className="grid grid-cols-12 mono text-[10px] text-[#808080] tracking-widest py-3 border-b-[0.5px] border-[#2A2A2A]">
          <div className="col-span-1">#</div>
          <div className="col-span-4">CLIENT</div>
          <div className="col-span-3">NACE SECTOR</div>
          <div className="col-span-1">YEAR</div>
          <div className="col-span-1">SCORE</div>
          <div className="col-span-1">STATUS</div>
          <div className="col-span-1 text-right">ACTIONS</div>
        </div>

        {loading && <div className="mono text-xs text-[#808080] py-8 ae-cursor">LOADING</div>}

        {!loading && audits.length === 0 && (
          <div className="mono text-xs text-[#808080] py-16 text-center">
            <div className="text-[#E8E8E8] mb-2 text-sm">NO AUDITS ON RECORD</div>
            <div>Trigger [+ NEW AUDIT] to begin.</div>
          </div>
        )}

        {audits.map((a, i) => (
          <div
            key={a.audit_id}
            data-testid={`audit-row-${a.audit_id}`}
            onClick={() => nav(`/audits/${a.audit_id}`)}
            className="grid grid-cols-12 mono text-xs items-center py-4 border-b-[0.5px] border-[#1A1A1A] hover:bg-[#0D0D0D] cursor-pointer transition-colors"
          >
            <div className="col-span-1 text-[#808080]">{String(i + 1).padStart(3, "0")}</div>
            <div className="col-span-4 sans text-[#E8E8E8] text-sm">{a.client_name}</div>
            <div className="col-span-3 text-[#808080] truncate pr-4">{a.nace_code} · {a.nace_name}</div>
            <div className="col-span-1 text-[#E8E8E8]">{a.reporting_year}</div>
            <div className="col-span-1 text-[#E8E8E8]">{a.compliance_score ?? "—"}</div>
            <div className={`col-span-1 ${statusColor[a.status] || "text-[#808080]"}`}>{a.status}</div>
            <div className="col-span-1 text-right">
              <button
                data-testid={`delete-audit-${a.audit_id}`}
                onClick={(e) => remove(a.audit_id, e)}
                className="text-[#808080] hover:text-[#FF0000]"
              >DEL</button>
            </div>
          </div>
        ))}
      </div>

      <NewAuditDrawer open={open} onClose={() => setOpen(false)} onCreated={onCreated} />
    </div>
  );
}
