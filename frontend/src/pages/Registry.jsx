import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

export default function Registry() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const workspace = params.get("workspace") || "";
  const [page, setPage] = useState(1);
  const [limit] = useState(25);
  const [data, setData] = useState({ entries: [], total: 0, has_next: false });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const wq = workspace ? `&workspace=${workspace}` : "";
    api.get(`/public/registry?page=${page}&limit=${limit}${wq}`)
      .then(r => setData(r.data))
      .catch(() => setData({ entries: [], total: 0, has_next: false }))
      .finally(() => setLoading(false));
  }, [page, limit, workspace]);

  const trunc = (h) => (h && h.length > 20 ? `${h.substr(0, 8)}…${h.substr(-8)}` : h || "—");

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8] flex flex-col">
      <header className="ae-border-strong border-b flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-8">
          <div className="mono text-xs tracking-[0.2em]">AUDITENGINE // TRUST ANCHOR</div>
          <div className="flex gap-6">
            <button onClick={() => nav("/verify")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white">⧉ VERIFY ROOT</button>
            <span className="mono text-[10px] tracking-widest text-[#00FF41]">⧉ GLOBAL ROOT REGISTRY</span>
            <button onClick={() => nav("/leaderboard")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white">⧉ LEADERBOARD</button>
          </div>
        </div>
        <div className="mono text-[10px] tracking-widest text-[#808080]">PUBLIC · READ-ONLY</div>
      </header>

      <main className="flex-1 px-8 py-14">
        <div className="max-w-6xl mx-auto">
          <div className="mono text-[10px] tracking-[0.3em] text-[#00FF41] mb-6">// GLOBAL ROOT REGISTRY</div>
          <h1 className="sans text-5xl font-light tracking-tight mb-3">
            The reference substrate.
          </h1>
          <p className="sans text-[#808080] text-base max-w-3xl leading-relaxed mb-10">
            The immutable record of all verified workspace attestations. A public proof of existence.
            Once a root is published here, it is a permanent, cryptographically-frozen record
            that the audit existed at that specific point in time.
          </p>

          {workspace && (
            <div className="ae-border-strong px-6 py-4 mb-6 flex items-center justify-between" data-testid="registry-workspace-filter">
              <div>
                <div className="mono text-[10px] tracking-[0.3em] text-[#00FF41]">// FILTERED · SINGLE WORKSPACE</div>
                <div className="mono text-xs text-[#E8E8E8] mt-2 break-all">{workspace}</div>
              </div>
              <button
                onClick={() => nav("/registry")}
                className="mono text-[10px] tracking-widest text-[#808080] hover:text-[#FF0000]"
                data-testid="registry-clear-filter"
              >CLEAR FILTER ✕</button>
            </div>
          )}

          <div className="ae-border-strong">
            <div className="ae-border-strong border-b px-6 py-4 flex items-center justify-between">
              <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// TRANSPARENCY LOG · {data.total.toString().padStart(6, "0")} ROOTS</div>
              <div className="mono text-[10px] text-[#808080]" data-testid="registry-pagination-info">
                PAGE {page.toString().padStart(3, "0")} · {loading ? "LOADING" : `SHOWING ${data.entries.length}`}
              </div>
            </div>

            <div className="grid grid-cols-12 mono text-[10px] tracking-widest text-[#808080] px-6 py-3 border-b-[0.5px] border-[#2A2A2A]">
              <div className="col-span-6">MERKLE ROOT</div>
              <div className="col-span-1">YEAR</div>
              <div className="col-span-1 text-right pr-6">AUDITS</div>
              <div className="col-span-4 pl-2">TIMESTAMP (UTC)</div>
            </div>

            {loading && <div className="mono text-xs text-[#808080] px-6 py-8 ae-cursor">LOADING REGISTRY</div>}

            {!loading && data.entries.length === 0 && (
              <div className="mono text-xs text-[#808080] px-6 py-16 text-center">
                <div className="text-[#E8E8E8] mb-2 text-sm">REGISTRY EMPTY</div>
                <div>No snapshots have been published yet.</div>
              </div>
            )}

            {!loading && data.entries.map((e) => (
              <button
                key={e.merkle_root}
                data-testid={`registry-row-${e.merkle_root.substr(0, 12)}`}
                onClick={() => nav(`/verify?root=${e.merkle_root}`)}
                className="w-full text-left grid grid-cols-12 mono text-xs items-center px-6 py-4 border-b-[0.5px] border-[#1A1A1A] hover:bg-[#0D0D0D] transition-colors"
              >
                <div className="col-span-6 text-[#00FF41] tracking-wider">
                  <span className="text-[#808080]">→ </span>{trunc(e.merkle_root)}
                </div>
                <div className="col-span-1 text-[#E8E8E8]">FY{e.reporting_year}</div>
                <div className="col-span-1 text-right pr-6 text-[#E8E8E8]">{String(e.audit_count).padStart(3, "0")}</div>
                <div className="col-span-4 pl-2 text-[#808080]">{e.generated_at}</div>
              </button>
            ))}

            {!loading && data.entries.length > 0 && (
              <div className="ae-border-strong border-t px-6 py-3 flex items-center justify-between">
                <button
                  data-testid="registry-prev"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className={`mono text-[10px] tracking-widest px-4 py-2 ae-border-strong ${page === 1 ? "text-[#333] cursor-not-allowed" : "text-[#808080] hover:text-white"}`}
                >← PREVIOUS</button>
                <div className="mono text-[10px] text-[#808080]">
                  {(page - 1) * limit + 1} — {(page - 1) * limit + data.entries.length} OF {data.total}
                </div>
                <button
                  data-testid="registry-next"
                  onClick={() => setPage(p => p + 1)}
                  disabled={!data.has_next}
                  className={`mono text-[10px] tracking-widest px-4 py-2 ae-border-strong ${!data.has_next ? "text-[#333] cursor-not-allowed" : "text-[#808080] hover:text-white"}`}
                >NEXT →</button>
              </div>
            )}
          </div>

          <div className="mt-10 mono text-[10px] text-[#808080] leading-relaxed max-w-3xl">
            The Global Root Registry publishes SHA-256 Merkle roots and metadata only.
            No workspace identifiers, no client names, no audit content ever appears in this log.
            Click any root to open the Trust Anchor verifier and confirm its integrity independently.
          </div>
        </div>
      </main>

      <footer className="ae-border-strong border-t px-8 py-3 mono text-[10px] text-[#808080] flex justify-between">
        <div>© AUDITENGINE // THE MIRROR OF CERTAINTY</div>
        <div>TRANSPARENCY LOG · IMMUTABLE</div>
      </footer>
    </div>
  );
}
