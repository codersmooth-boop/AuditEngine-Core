import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL;

const ENDPOINTS = [
  {
    path: "/api/regulator/sandbox/whoami",
    label: "// WHOAMI",
    desc: "Echoes the organization on the key, expiry, and current Registry Master Root. Useful as a live handshake.",
    tone: "#E8E8E8",
  },
  {
    path: "/api/regulator/sandbox/adoption",
    label: "// ADOPTION",
    desc: "Compliance-score distribution grouped by NACE section (letter). Averages, min/max, critical-findings totals — never identities.",
    tone: "#00FF41",
  },
  {
    path: "/api/regulator/sandbox/streaks",
    label: "// SYSTEMIC HEALTH",
    desc: "Streak-longevity histogram — how many workspaces are sustaining N consecutive years of verified attestation.",
    tone: "#FFD700",
  },
  {
    path: "/api/regulator/sandbox/scores",
    label: "// DISTRIBUTION",
    desc: "10-point bucketed histogram of compliance scores across every completed audit in the Registry.",
    tone: "#00FF41",
  },
  {
    path: "/api/regulator/sandbox/volatility",
    label: "// VOLATILITY",
    desc: "Year-over-year frequency of HIGH greenwashing risk and sub-60 non-compliance across the entire network.",
    tone: "#FF0000",
  },
];

export default function Regulator() {
  const nav = useNavigate();
  const [apiKey, setApiKey] = useState("");
  const [selected, setSelected] = useState(ENDPOINTS[0].path);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);
  const [payload, setPayload] = useState("");
  const [error, setError] = useState("");

  async function execute() {
    if (!apiKey.trim()) {
      setError("X-Regulator-Key required.");
      setPayload("");
      setStatus(null);
      return;
    }
    setBusy(true);
    setError("");
    setPayload("");
    setStatus(null);
    try {
      const res = await fetch(`${API}${selected}`, {
        headers: { "X-Regulator-Key": apiKey.trim() },
      });
      setStatus(res.status);
      const text = await res.text();
      try {
        setPayload(JSON.stringify(JSON.parse(text), null, 2));
      } catch {
        setPayload(text);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8] flex flex-col">
      <header className="ae-border-strong border-b flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-8">
          <div className="mono text-xs tracking-[0.2em]" data-testid="regulator-header-title">
            AUDITENGINE // TRUST ANCHOR
          </div>
          <div className="flex gap-6">
            <button onClick={() => nav("/verify")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-verify">⧉ VERIFY ROOT</button>
            <button onClick={() => nav("/registry")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-registry">⧉ GLOBAL ROOT REGISTRY</button>
            <button onClick={() => nav("/leaderboard")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-leaderboard">⧉ LEADERBOARD</button>
            <span className="mono text-[10px] tracking-widest text-[#00FF41]" data-testid="nav-regulator-active">⧉ REGULATOR SANDBOX</span>
          </div>
        </div>
        <div className="mono text-[10px] tracking-widest text-[#808080]">INSTITUTIONAL · READ-ONLY</div>
      </header>

      <main className="flex-1 px-8 py-14">
        <div className="max-w-6xl mx-auto">
          <div className="mono text-[10px] tracking-[0.3em] text-[#00FF41] mb-6">// REGULATOR SANDBOX</div>
          <h1 className="sans text-5xl font-light tracking-tight mb-3" data-testid="regulator-heading">
            The reporting substrate.
          </h1>
          <p className="sans text-[#808080] text-base max-w-3xl leading-relaxed mb-12">
            A time-boxed, aggregation-only interface for regulators, supervisory authorities, and policy
            analysts. Query the Registry as a whole — sector adoption, systemic health, distribution curves,
            volatility across the network — without ever touching a single client identity.
          </p>

          {/* Endpoint cards */}
          <div className="grid grid-cols-2 gap-0 ae-border-strong mb-12">
            {ENDPOINTS.slice(1).map((e, i) => (
              <button
                type="button"
                key={e.path}
                data-testid={`regulator-endpoint-${i}`}
                onClick={() => setSelected(e.path)}
                className={`text-left p-8 transition-opacity ${i % 2 === 0 ? "border-r-[0.5px]" : ""} ${i < 2 ? "border-b-[0.5px]" : ""} border-[#2A2A2A] ${selected === e.path ? "bg-[#050505]" : "hover:bg-[#050505]"}`}
              >
                <div className="mono text-[10px] tracking-[0.3em]" style={{ color: e.tone }}>{e.label}</div>
                <div className="mono text-sm text-[#E8E8E8] mt-3 break-all">GET {e.path}</div>
                <p className="sans text-sm text-[#E8E8E8] leading-relaxed mt-3">{e.desc}</p>
                {selected === e.path && (
                  <div className="mono text-[9px] tracking-widest text-[#00FF41] mt-4">▸ SELECTED</div>
                )}
              </button>
            ))}
          </div>

          {/* LIVE TERMINAL */}
          <div className="ae-border-strong mb-12" data-testid="regulator-terminal">
            <div className="ae-border-strong border-b px-6 py-4 flex justify-between items-center">
              <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// LIVE TERMINAL · READ-ONLY QUERY</div>
              <div className="mono text-[10px] tracking-widest text-[#808080]">10 REQ/MIN · PER KEY</div>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-[110px_1fr_140px] gap-0 ae-border-strong">
                <div className="mono text-[10px] tracking-widest text-[#808080] px-4 py-3 border-r-[0.5px] border-[#2A2A2A] flex items-center">X-REG-KEY</div>
                <input
                  data-testid="regulator-key-input"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="reg_…"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="bg-black text-[#00FF41] mono text-sm px-4 py-3 outline-none border-r-[0.5px] border-[#2A2A2A]"
                />
                <button
                  data-testid="regulator-execute-btn"
                  onClick={execute}
                  disabled={busy}
                  className="mono text-[11px] tracking-widest text-black bg-[#00FF41] hover:bg-white disabled:bg-[#333] disabled:text-[#808080] px-4"
                >
                  {busy ? "EXECUTING…" : "▸ EXECUTE"}
                </button>
              </div>
              <div className="grid grid-cols-[110px_1fr] gap-0 ae-border-strong">
                <div className="mono text-[10px] tracking-widest text-[#808080] px-4 py-3 border-r-[0.5px] border-[#2A2A2A] flex items-center">ENDPOINT</div>
                <div className="mono text-sm text-[#E8E8E8] px-4 py-3" data-testid="regulator-selected-endpoint">GET {selected}</div>
              </div>

              {/* Status bar */}
              <div className="ae-border-strong px-4 py-3 flex justify-between items-center">
                <div className="mono text-[10px] tracking-widest text-[#808080]">STATUS</div>
                <div
                  className="mono text-xs tracking-widest"
                  style={{ color: status == null ? "#808080" : status === 200 ? "#00FF41" : status === 429 ? "#FFBF00" : "#FF0000" }}
                  data-testid="regulator-status"
                >
                  {status == null ? "IDLE" : status === 200 ? `200 · OK` : status === 401 ? "401 · UNAUTHORIZED" : status === 429 ? "429 · RATE LIMITED" : `${status} · ERROR`}
                </div>
              </div>

              {error && (
                <div className="ae-border-strong px-4 py-3 mono text-xs text-[#FF0000]" data-testid="regulator-error">{error}</div>
              )}

              <div className="ae-border-strong">
                <div className="border-b-[0.5px] border-[#2A2A2A] px-4 py-2 mono text-[10px] tracking-widest text-[#808080]">RESPONSE PAYLOAD</div>
                <pre
                  data-testid="regulator-response"
                  className="mono text-[11px] leading-relaxed text-[#E8E8E8] px-4 py-3 overflow-x-auto whitespace-pre max-h-[420px] overflow-y-auto"
                >
{payload || "// awaiting execution…"}
                </pre>
              </div>
            </div>
          </div>

          {/* Privacy guardrails */}
          <div className="ae-border-strong mb-12">
            <div className="ae-border-strong border-b px-6 py-4">
              <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// PRIVACY GUARDRAILS</div>
            </div>
            <div className="grid grid-cols-3 gap-0">
              <Cell label="K-ANONYMITY THRESHOLD" value="05" note="Buckets with fewer than K entries are suppressed at the aggregation layer, not after." />
              <Cell label="IDENTITY FIELDS EXPOSED" value="ZERO" note="No client names, no workspace IDs, no findings." border />
              <Cell label="ACCESS CONTROL" value="30-DAY KEY" note="X-Regulator-Key header. Auto-expires per TTL." border />
            </div>
          </div>

          {/* Cross-verification note */}
          <div className="ae-border-strong mb-12">
            <div className="ae-border-strong border-b px-6 py-4">
              <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// CROSS-VERIFICATION</div>
            </div>
            <div className="p-6 space-y-3">
              <p className="sans text-sm text-[#E8E8E8] leading-relaxed">
                Every sandbox response includes a <span className="mono text-[#00FF41]">registry_master_root</span> — a rolling SHA-256
                digest over every attested Merkle Root in the public Registry, in chronological order. Regulators can pin this value
                at query time and audit-trail it. Any retroactive insertion or edit to the Registry will change the master root and
                be provably detectable.
              </p>
            </div>
          </div>

          {/* Authentication */}
          <div className="ae-border-strong mb-12">
            <div className="ae-border-strong border-b px-6 py-4">
              <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// AUTHENTICATION</div>
            </div>
            <div className="p-6 space-y-4">
              <p className="sans text-sm text-[#E8E8E8] leading-relaxed">
                All sandbox endpoints require a time-boxed regulator key issued by AuditEngine.
                Keys are opaque strings scoped per organization, revocable on demand, and self-expire after their TTL.
              </p>
              <div className="ae-border-strong px-4 py-3 mono text-[11px] text-[#00FF41] break-all" data-testid="regulator-example-curl">
                curl -H "X-Regulator-Key: reg_&lt;opaque_token&gt;" &lt;backend_url&gt;/api/regulator/sandbox/adoption
              </div>
              <div className="mono text-[10px] text-[#808080]">
                Access requests: contact institutions@auditengine.example with your organization's official domain.
              </div>
            </div>
          </div>

          <div className="mono text-[10px] text-[#808080] leading-relaxed max-w-3xl">
            The Regulator Sandbox is designed to be cited in policy documents.
            The k-anonymity threshold is <span className="text-[#E8E8E8]">structurally enforced</span>: any bucket below the threshold is
            <span className="text-[#E8E8E8]"> silently suppressed at the aggregation layer</span>, not filtered after the fact.
            No amount of clever querying can recover a single workspace's contribution.
          </div>
        </div>
      </main>

      <footer className="ae-border-strong border-t px-8 py-3 mono text-[10px] text-[#808080] flex justify-between">
        <div>© AUDITENGINE // THE MIRROR OF CERTAINTY</div>
        <div>REGULATOR SANDBOX · INSTITUTIONAL SUBSTRATE</div>
      </footer>
    </div>
  );
}

function Cell({ label, value, note, border = false }) {
  return (
    <div className={`p-6 ${border ? "border-l-[0.5px] border-[#2A2A2A]" : ""}`}>
      <div className="mono text-[10px] text-[#808080] tracking-widest">{label}</div>
      <div className="mono text-2xl text-[#00FF41] mt-3">{value}</div>
      <div className="mono text-[10px] text-[#808080] mt-2 leading-relaxed">{note}</div>
    </div>
  );
}
