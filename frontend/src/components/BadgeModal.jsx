import React, { useEffect, useState } from "react";
import { api, API } from "../lib/api";

export default function BadgeModal({ year, onClose }) {
  const [meta, setMeta] = useState(null); // {merkle_root, reporting_year, audit_count, generated_at}
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get(`/ledger/snapshot-meta`, { params: { year } });
        setMeta(r.data);
      } catch (e) {
        setError(e?.response?.data?.detail || "Failed to compute snapshot root");
      }
    })();
  }, [year]);

  const badgeUrl = meta ? `${API}/public/badge/${meta.merkle_root}.svg` : "";
  const verifyUrl = meta ? `${window.location.origin}/verify?root=${meta.merkle_root}` : "";
  const embed = meta ? `<a href="${verifyUrl}" target="_blank" rel="noopener"><img src="${badgeUrl}" alt="Verified by AuditEngine · ${meta.merkle_root.substr(0,8)}…${meta.merkle_root.substr(-8)}" width="280" height="88" /></a>` : "";

  const copy = async () => {
    try { await navigator.clipboard.writeText(embed); setCopied(true); setTimeout(() => setCopied(false), 1600); }
    catch { /* ignore */ }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" data-testid="badge-modal">
      <div className="absolute inset-0 bg-black/80" onClick={onClose} />
      <div className="relative w-full max-w-3xl bg-black ae-border-strong">
        <div className="ae-border-strong border-b p-6 flex items-center justify-between">
          <div>
            <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// SIGNED ATTESTATION BADGE</div>
            <h2 className="sans text-2xl mt-1 font-light">The public seal of certainty.</h2>
          </div>
          <button data-testid="badge-close" onClick={onClose} className="mono text-xs text-[#808080] hover:text-[#FF0000]">CLOSE ✕</button>
        </div>

        <div className="p-6 space-y-6">
          {error && <div className="mono text-xs text-[#FF0000]">! {error}</div>}
          {!meta && !error && <div className="mono text-xs text-[#808080] ae-cursor">COMPUTING MERKLE ROOT</div>}

          {meta && (
            <>
              <div>
                <div className="mono text-[10px] text-[#808080] tracking-widest mb-3">// PREVIEW</div>
                <div className="ae-border-strong p-8 flex items-center justify-center bg-[#050505]">
                  {/* Live SVG preview via the public endpoint */}
                  <img src={badgeUrl} alt="Attestation badge" width={280} height={88} data-testid="badge-preview" />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-0 ae-border-strong">
                <Cell label="REPORTING YEAR" value={`FY${meta.reporting_year}`} testid="badge-year" />
                <Cell label="AUDITS ATTESTED" value={String(meta.audit_count).padStart(3, "0")} testid="badge-count" border />
                <Cell label="MERKLE ROOT" value={`${meta.merkle_root.substr(0, 8)}…${meta.merkle_root.substr(-8)}`} valueClass="text-[#00FF41]" testid="badge-root" border />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="mono text-[10px] text-[#808080] tracking-widest">// EMBED CODE (HTML)</div>
                  <button
                    data-testid="badge-copy"
                    onClick={copy}
                    className="mono text-[10px] tracking-widest px-4 py-2 ae-border-strong bg-black text-[#E8E8E8] hover:bg-[#0D0D0D]"
                  >{copied ? "✓ COPIED" : "COPY EMBED CODE"}</button>
                </div>
                <textarea
                  data-testid="badge-embed"
                  readOnly
                  value={embed}
                  onFocus={(e) => e.target.select()}
                  className="w-full h-28 bg-[#050505] ae-border-strong px-4 py-3 mono text-[11px] text-[#00FF41] focus:outline-none resize-none"
                />
              </div>

              <div>
                <div className="mono text-[10px] text-[#808080] tracking-widest mb-2">// DIRECT DEEP-LINK</div>
                <div className="ae-border-strong px-4 py-3 mono text-[11px] text-[#00FF41] break-all" data-testid="badge-deeplink">{verifyUrl}</div>
              </div>

              <div>
                <div className="mono text-[10px] text-[#808080] tracking-widest mb-2">// RAW SVG URL</div>
                <div className="ae-border-strong px-4 py-3 mono text-[11px] text-[#808080] break-all">{badgeUrl}</div>
              </div>

              <div className="mono text-[10px] text-[#808080] leading-relaxed">
                Drop the embed code into any sustainability report, investor deck, or website.
                The badge is a static SVG — zero external JS, zero runtime dependencies.
                Every click deep-links a third party into the Trust Anchor, which auto-verifies the root against the Global Registry.
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Cell({ label, value, valueClass = "text-[#E8E8E8]", border = false, testid }) {
  return (
    <div className={`px-6 py-5 ${border ? "border-l-[0.5px] border-[#2A2A2A]" : ""}`} data-testid={testid}>
      <div className="mono text-[10px] text-[#808080] tracking-widest">{label}</div>
      <div className={`mono text-lg mt-2 ${valueClass}`}>{value}</div>
    </div>
  );
}
