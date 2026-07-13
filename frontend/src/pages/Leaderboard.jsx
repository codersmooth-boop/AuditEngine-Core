import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export default function Leaderboard() {
  const nav = useNavigate();
  const [data, setData] = useState({ entries: [], total_workspaces: 0, cached_at: null });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/public/leaderboard").then(r => setData(r.data)).finally(() => setLoading(false));
  }, []);

  const trunc = (h) => (h && h.length > 20 ? `${h.substr(0, 10)}…${h.substr(-10)}` : h || "—");
  const rankTone = (r) => r === 1 ? "#00FF41" : r <= 3 ? "#FFBF00" : "#E8E8E8";

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8] flex flex-col">
      <header className="ae-border-strong border-b flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-8">
          <div className="mono text-xs tracking-[0.2em]">AUDITENGINE // TRUST ANCHOR</div>
          <div className="flex gap-6">
            <button onClick={() => nav("/verify")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white">⧉ VERIFY ROOT</button>
            <button onClick={() => nav("/registry")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white">⧉ GLOBAL ROOT REGISTRY</button>
            <span className="mono text-[10px] tracking-widest text-[#00FF41]">⧉ LEADERBOARD</span>
          </div>
        </div>
        <div className="mono text-[10px] tracking-widest text-[#808080]">PUBLIC · CACHED · READ-ONLY</div>
      </header>

      <main className="flex-1 px-8 py-14">
        <div className="max-w-6xl mx-auto">
          <div className="mono text-[10px] tracking-[0.3em] text-[#00FF41] mb-6">// GLOBAL TRUST LEADERBOARD</div>
          <h1 className="sans text-5xl font-light tracking-tight mb-3">
            The market's compliance index.
          </h1>
          <p className="sans text-[#808080] text-base max-w-3xl leading-relaxed mb-10">
            The definitive ranking of organizations by verified audit volume. A public index of transparency
            and structural integrity. Every rank on this leaderboard is backed by a mathematically-frozen Merkle
            root in the Global Registry.
          </p>

          <div className="ae-border-strong">
            <div className="ae-border-strong border-b px-6 py-4 flex items-center justify-between">
              <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">
                // RANKED WORKSPACES · {String(data.total_workspaces).padStart(4, "0")}
              </div>
              <div className="mono text-[10px] text-[#808080]">
                {data.cached_at ? `CACHED · ${data.cached_at.substr(0, 19).replace("T", " ")} UTC` : "LIVE"}
              </div>
            </div>

            <div className="grid grid-cols-12 mono text-[10px] tracking-widest text-[#808080] px-6 py-3 border-b-[0.5px] border-[#2A2A2A]">
              <div className="col-span-1">RANK</div>
              <div className="col-span-6">WORKSPACE HASH</div>
              <div className="col-span-2 text-right pr-6">TOTAL AUDITS</div>
              <div className="col-span-3 pl-2">LAST ATTESTATION (UTC)</div>
            </div>

            {loading && <div className="mono text-xs text-[#808080] px-6 py-8 ae-cursor">LOADING RANKINGS</div>}

            {!loading && data.entries.length === 0 && (
              <div className="mono text-xs text-[#808080] px-6 py-16 text-center">
                <div className="text-[#E8E8E8] mb-2 text-sm">LEADERBOARD EMPTY</div>
                <div>No workspaces have opted in yet. Be the first to claim a rank.</div>
              </div>
            )}

            {!loading && data.entries.map((e) => (
              <button
                key={e.workspace_id_hashed}
                data-testid={`leaderboard-row-${e.rank}`}
                onClick={() => nav(`/registry?workspace=${e.workspace_id_hashed}`)}
                className="w-full text-left grid grid-cols-12 mono text-xs items-center px-6 py-5 border-b-[0.5px] border-[#1A1A1A] hover:bg-[#0D0D0D] transition-colors"
              >
                <div className="col-span-1 mono text-2xl" style={{ color: rankTone(e.rank) }}>
                  {String(e.rank).padStart(3, "0")}
                </div>
                <div className="col-span-6">
                  <div className="text-[#00FF41] tracking-wider">
                    <span className="text-[#808080]">→ </span>{trunc(e.workspace_id_hashed)}
                  </div>
                  <div className="mono text-[10px] text-[#808080] mt-1">
                    {e.snapshot_count} snapshot{e.snapshot_count === 1 ? "" : "s"} · first attestation {(e.first_attestation_date || "").substr(0, 10)}
                  </div>
                </div>
                <div className="col-span-2 text-right pr-6 text-[#00FF41] font-bold text-lg">
                  {String(e.total_audits).padStart(4, "0")}
                </div>
                <div className="col-span-3 pl-2 text-[#808080]">{e.last_attestation_date}</div>
              </button>
            ))}
          </div>

          <div className="mt-12 ae-border-strong p-8 flex items-center justify-between">
            <div>
              <div className="mono text-[10px] tracking-[0.3em] text-[#808080] mb-2">// NOT LISTED?</div>
              <div className="sans text-2xl font-light">Secure your rank. Build your Mirror.</div>
              <div className="mono text-xs text-[#808080] mt-2">Opt in from your workspace settings after your first snapshot.</div>
            </div>
            <a
              href="/"
              data-testid="leaderboard-cta"
              className="mono text-xs tracking-[0.2em] ae-border-strong px-8 py-4 bg-[#00FF41] text-black hover:bg-white transition-colors"
            >→ ENTER TERMINAL</a>
          </div>
        </div>
      </main>

      <footer className="ae-border-strong border-t px-8 py-3 mono text-[10px] text-[#808080] flex justify-between">
        <div>© AUDITENGINE // THE MIRROR OF CERTAINTY</div>
        <div>LEADERBOARD · CACHED 60s · IMMUTABLE UNDERLYING PROOFS</div>
      </footer>
    </div>
  );
}
