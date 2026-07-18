import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { listAudits, deleteAudit, setLeaderboardOptIn, api } from "../lib/api";
import NewAuditDrawer from "../components/NewAuditDrawer";
import UtcClock from "../components/UtcClock";
import ProvisionAccessLink from "../components/ProvisionAccessLink";
import ConfirmDialog from "../components/ConfirmDialog";

export default function Dashboard() {
  const { user, logout, refresh } = useAuth();
  const [audits, setAudits] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [optSaving, setOptSaving] = useState(false);
  const [streak, setStreak] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const nav = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      setAudits(await listAudits());
      try { const r = await api.get("/settings/streak"); setStreak(r.data); } catch { /* ignore */ }
    } finally { setLoading(false); }
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

  const remove = (id, e) => {
    e.stopPropagation();
    setPendingDelete(id);
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    const id = pendingDelete;
    setPendingDelete(null);
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
            <button data-testid="nav-verify" onClick={() => nav("/verify")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white">⧉ VERIFY ROOT</button>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <UtcClock />
          <ProvisionAccessLink />
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

      {/* STREAK STATUS PANEL */}
      {streak && (
        <div className="ae-border-strong border-b px-8 py-5 grid grid-cols-3 gap-0" data-testid="streak-status-panel">
          <div className="border-r-[0.5px] border-[#2A2A2A] pr-6">
            <div className="mono text-[10px] tracking-widest text-[#808080]">// TRUST STREAK</div>
            <div className="flex items-baseline gap-3 mt-2">
              <span className="mono text-4xl" style={{ color: streak.current_streak > 0 ? "#FFD700" : "#808080" }}>
                ★ {String(streak.current_streak).padStart(2, "0")}
              </span>
              <span className="mono text-xs text-[#808080]">YEAR{streak.current_streak === 1 ? "" : "S"}</span>
            </div>
          </div>
          <div className="border-r-[0.5px] border-[#2A2A2A] px-6">
            <div className="mono text-[10px] tracking-widest text-[#808080]">// LAST ATTESTED</div>
            <div className="mono text-3xl text-[#E8E8E8] mt-2">{streak.last_streak_year ?? "—"}</div>
          </div>
          <div className="pl-6" data-testid="streak-status-text">
            <div className="mono text-[10px] tracking-widest text-[#808080]">// STATUS</div>
            {streak.current_streak === 0 && (
              <div className="mono text-sm text-[#E8E8E8] mt-2">
                No streak yet. Publish your first FY{streak.current_year - 1} snapshot to start.
              </div>
            )}
            {streak.current_streak > 0 && !streak.at_risk && (
              <div className="mono text-sm mt-2" style={{ color: "#00FF41" }}>
                CURRENT STREAK: ★ {String(streak.current_streak).padStart(2, "0")} YEAR{streak.current_streak === 1 ? "" : "S"}. Next attestation due: FY{streak.next_due_year}.
              </div>
            )}
            {streak.current_streak > 0 && streak.at_risk && (
              <div className="mono text-sm mt-2" style={{ color: "#FFBF00" }}>
                STREAK AT RISK. Publish FY{streak.current_year - 1} snapshot to maintain your rank.
              </div>
            )}
          </div>
        </div>
      )}

      <div className="px-8 py-6">
        <div className="grid grid-cols-12 mono text-[10px] text-[#808080] tracking-widest py-3 border-b-[0.5px] border-[#2A2A2A]">
          <div className="col-span-1">#</div>
          <div className="col-span-2">CLIENT</div>
          <div className="col-span-3">NACE SECTOR</div>
          <div className="col-span-1">YEAR</div>
          <div className="col-span-1">SCORE</div>
          <div className="col-span-1">STATUS</div>
          <div className="col-span-2 text-right">CREATED · UTC</div>
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
            <div className="col-span-2 sans text-[#E8E8E8] text-sm truncate pr-3">{a.client_name}</div>
            <div className="col-span-3 text-[#808080] truncate pr-4">{a.nace_code} · {a.nace_name}</div>
            <div className="col-span-1 text-[#E8E8E8]">{a.reporting_year}</div>
            <div className="col-span-1 text-[#E8E8E8]">{a.compliance_score ?? "—"}</div>
            <div className={`col-span-1 ${statusColor[a.status] || "text-[#808080]"}`}>{a.status}</div>
            <div className="col-span-2 text-right text-[#808080]" data-testid={`audit-created-${a.audit_id}`}>
              {a.created_at ? `${String(a.created_at).replace("T", " · ").slice(0, 19)}Z` : "—"}
            </div>
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

      <ConfirmDialog
        open={!!pendingDelete}
        title="// CONFIRM DELETION"
        message="This audit will be removed from the workspace. The Merkle Root — once minted — persists permanently in the public registry."
        confirmLabel="▸ EXECUTE"
        cancelLabel="← ABORT"
        tone="#FF0000"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
        testid="delete-audit-confirm"
      />
    </div>
  );
}
