import React, { useState } from "react";
import { api } from "../lib/api";

export default function Verify() {
  const [root, setRoot] = useState("");
  const [state, setState] = useState("idle"); // idle | loading | verified | not_found | invalid | error
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const verify = async (e) => {
    e?.preventDefault();
    const cleaned = root.trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/.test(cleaned)) {
      setState("invalid"); setError("Merkle Root must be a 64-character hexadecimal SHA-256 string.");
      return;
    }
    setState("loading"); setError("");
    try {
      const r = await api.get(`/public/verify/${cleaned}`);
      setData(r.data);
      setState("verified");
    } catch (err) {
      const code = err?.response?.status;
      if (code === 404) setState("not_found");
      else if (code === 400) { setState("invalid"); setError(err?.response?.data?.status || "INVALID"); }
      else setState("error");
    }
  };

  const reset = () => { setState("idle"); setData(null); setError(""); };

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8] flex flex-col">
      <header className="ae-border-strong border-b flex items-center justify-between px-8 py-4">
        <div className="mono text-xs tracking-[0.2em]">AUDITENGINE // TRUST ANCHOR</div>
        <div className="mono text-[10px] tracking-widest text-[#808080]">PUBLIC VERIFICATION PORTAL</div>
      </header>

      <main className="flex-1 flex items-center justify-center px-8 py-16">
        <div className="w-full max-w-3xl">
          <div className="mono text-[10px] tracking-[0.3em] text-[#808080] mb-6">// VERIFY WORKSPACE INTEGRITY</div>
          <h1 className="sans text-5xl font-light tracking-tight mb-3">
            Prove the ledger.<br />Without seeing the ledger.
          </h1>
          <p className="sans text-[#808080] text-base max-w-2xl leading-relaxed mb-10">
            Paste a Master Merkle Root from an AuditEngine Statutory Snapshot to confirm the
            existence and integrity of the workspace attestation. No confidential audit data is exposed.
          </p>

          <form onSubmit={verify} className="ae-border-strong">
            <div className="ae-border-strong border-b px-4 py-2 flex items-center justify-between">
              <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// MASTER MERKLE ROOT · SHA-256</div>
              <div className="mono text-[10px] text-[#808080]">64 HEX</div>
            </div>
            <input
              data-testid="verify-input"
              value={root}
              onChange={(e) => { setRoot(e.target.value); if (state !== "idle") reset(); }}
              placeholder="e.g. c61c4f49d7568c67…"
              spellCheck={false}
              autoComplete="off"
              className="w-full bg-black text-[#00FF41] mono text-sm px-4 py-4 focus:outline-none border-b-[0.5px] border-[#1A1A1A]"
              style={{ letterSpacing: "0.05em" }}
            />
            <div className="flex">
              <button
                type="submit"
                data-testid="verify-submit"
                disabled={state === "loading"}
                className={`flex-1 mono text-xs tracking-[0.3em] px-6 py-4 transition-colors ${state === "loading" ? "bg-[#0D0D0D] text-[#808080]" : "bg-[#00FF41] text-black hover:bg-white"}`}
              >
                {state === "loading" ? "VERIFYING..." : "→ VERIFY INTEGRITY"}
              </button>
            </div>
          </form>

          {/* Result states */}
          <div className="mt-8">
            {state === "invalid" && (
              <div className="ae-border-strong p-6 ae-fade-in" data-testid="verify-invalid">
                <div className="mono text-lg text-[#FFBF00] tracking-widest">[INVALID INPUT]</div>
                <div className="mono text-xs text-[#808080] mt-3">{error}</div>
              </div>
            )}
            {state === "not_found" && (
              <div className="ae-border-strong p-6 ae-fade-in" data-testid="verify-notfound">
                <div className="mono text-lg text-[#FF0000] tracking-widest">[NOT FOUND]</div>
                <div className="mono text-xs text-[#808080] mt-3">No workspace snapshot exists for this Merkle root. The root may be fabricated, mistyped, or from a system outside the AuditEngine trust anchor.</div>
              </div>
            )}
            {state === "error" && (
              <div className="ae-border-strong p-6 ae-fade-in">
                <div className="mono text-lg text-[#FF0000] tracking-widest">[LOOKUP FAILED]</div>
                <div className="mono text-xs text-[#808080] mt-3">Trust anchor unreachable. Please retry.</div>
              </div>
            )}

            {state === "verified" && data && (
              <div className="ae-fade-in" data-testid="verify-certificate">
                <div className="ae-border-strong">
                  <div className="ae-border-strong border-b px-6 py-4 flex items-center justify-between">
                    <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// CERTIFICATE OF INTEGRITY</div>
                    <div className="mono text-2xl text-[#00FF41] tracking-widest" data-testid="verify-verified-header">[VERIFIED]</div>
                  </div>
                  <div className="grid grid-cols-2">
                    <Cell label="WORKSPACE HASH" value={data.workspace_id_hashed} mono valueClass="text-[#E8E8E8] break-all" testid="verify-workspace" />
                    <Cell label="AUDIT COUNT" value={String(data.audit_count).padStart(3, "0")} mono big testid="verify-count" />
                    <Cell label="REPORTING YEAR" value={data.reporting_year ?? "—"} mono big testid="verify-year" border />
                    <Cell label="GENERATION TIMESTAMP (UTC)" value={data.timestamp} mono valueClass="text-[#00FF41] break-all" testid="verify-timestamp" border />
                  </div>
                  <div className="ae-border-strong border-t px-6 py-6">
                    <div className="mono text-[10px] tracking-[0.3em] text-[#808080] mb-3">// STATEMENT OF NON-REPUDIATION</div>
                    <p className="sans text-sm text-[#E8E8E8] leading-relaxed">
                      This root is a mathematically frozen fingerprint of the workspace ledger.
                      Any alteration to the source data would invalidate this root.
                    </p>
                    <div className="mono text-[10px] text-[#00FF41] mt-4 break-all">MERKLE ROOT: {root.trim().toLowerCase()}</div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-10 mono text-[10px] text-[#808080] leading-relaxed max-w-2xl">
            The Trust Anchor exposes existence and integrity metadata only — no client identities,
            no findings, no financial figures. Verification does not require an account.
          </div>
        </div>
      </main>

      <footer className="ae-border-strong border-t px-8 py-3 mono text-[10px] text-[#808080] flex justify-between">
        <div>© AUDITENGINE // THE MIRROR OF CERTAINTY</div>
        <div>PUBLIC · NO AUTH REQUIRED</div>
      </footer>
    </div>
  );
}

function Cell({ label, value, mono = false, big = false, border = false, valueClass = "text-[#E8E8E8]", testid }) {
  return (
    <div
      data-testid={testid}
      className={`px-6 py-6 border-r-[0.5px] border-[#2A2A2A] last:border-r-0 ${border ? "border-t-[0.5px]" : ""}`}
    >
      <div className="mono text-[10px] text-[#808080] tracking-widest">{label}</div>
      <div className={`${mono ? "mono" : "sans"} ${big ? "text-4xl" : "text-xs"} mt-3 ${valueClass}`}>{value}</div>
    </div>
  );
}
