import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { getBillingTier, createPortalSession } from "../lib/api";

const API = process.env.REACT_APP_BACKEND_URL;

// Obfuscated Enterprise contact — assembled at click time so no email literal
// exists in the served HTML/JS.
const ENT_LOCAL = [99, 111, 100, 101, 114, 115, 109, 111, 111, 116, 104]; // "codersmooth"
const ENT_DOMAIN = [103, 109, 97, 105, 108, 46, 99, 111, 109];             // "gmail.com"

function assembleEnterpriseHref() {
  const local = String.fromCharCode(...ENT_LOCAL);
  const domain = String.fromCharCode(...ENT_DOMAIN);
  const subject = encodeURIComponent("AuditEngine · Enterprise Inquiry");
  const body = encodeURIComponent(
    "Organization:\nExpected audit volume / year:\nDeployment model (SaaS / VPC / On-prem):\n",
  );
  return `mailto:${local}\u0040${domain}?subject=${subject}&body=${body}`;
}

const PLANS = [
  {
    plan_id: "professional_monthly",
    tag: "// PROFESSIONAL",
    price: "€49",
    cadence: "/ month",
    accent: "#E8E8E8",
    cta: "▸ SUBSCRIBE",
    features: [
      "Unlimited ESG Audits",
      "Board Brief + PDF",
      "Merkle-Root Snapshots",
      "Trust Anchor Microsite",
      "Regulator Sandbox",
      "Public Attestation",
    ],
  },
  {
    plan_id: "annual_yearly",
    tag: "// ANNUAL",
    price: "€490",
    cadence: "/ year",
    accent: "#00FF41",
    cta: "▸ SUBSCRIBE",
    featured: true,
    features: [
      "Everything in Professional",
      "Priority Throughput",
      "Gold Ledger Lock",
      "Dedicated Onboarding",
      "Signed Policy Letter",
    ],
  },
  {
    plan_id: "enterprise",
    tag: "// ENTERPRISE",
    price: "Bespoke",
    cadence: "· quoted",
    accent: "#FFD700",
    cta: "▸ CONTACT",
    features: [
      "Everything in Annual",
      "VPC / On-prem",
      "Custom Taxonomies",
      "Volume Regulator Keys",
      "SLA + Liaison",
      "White-label Mirror",
    ],
  },
];

// Max rows across tiers → so cells align in the grid.
const MAX_ROWS = Math.max(...PLANS.map((p) => p.features.length));

export default function Pricing() {
  const nav = useNavigate();
  const { user } = useAuth();
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState("");
  const [tier, setTier] = useState(null); // {active, tier, plan_id}

  useEffect(() => {
    if (!user) { setTier({ active: false, tier: "free", plan_id: null }); return; }
    let cancelled = false;
    (async () => {
      try {
        const t = await getBillingTier();
        if (!cancelled) setTier(t);
      } catch {
        if (!cancelled) setTier({ active: false, tier: "free", plan_id: null });
      }
    })();
    return () => { cancelled = true; };
  }, [user]);

  async function subscribe(plan_id) {
    setBusy(plan_id);
    setErr("");
    try {
      const res = await fetch(`${API}/api/payments/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_id,
          origin_url: window.location.origin,
          user_id: user?.user_id || null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      window.location.href = data.checkout_url;
    } catch (e) {
      setErr(String(e));
      setBusy(null);
    }
  }

  async function openPortal() {
    setBusy("portal");
    setErr("");
    try {
      const { portal_url } = await createPortalSession(`${window.location.origin}/pricing`);
      window.location.href = portal_url;
    } catch (e) {
      setErr(String(e));
      setBusy(null);
    }
  }

  function contactEnterprise(e) {
    e.preventDefault();
    window.location.href = assembleEnterpriseHref();
  }

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8] flex flex-col">
      <header className="ae-border-strong border-b flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-8">
          <button
            onClick={() => nav("/")}
            className="mono text-xs tracking-[0.2em] hover:text-white"
            data-testid="pricing-brand"
          >
            AUDITENGINE // PRICING SPECIFICATIONS
          </button>
          <div className="flex gap-6">
            <button onClick={() => nav("/verify")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-verify">⧉ VERIFY ROOT</button>
            <button onClick={() => nav("/registry")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-registry">⧉ REGISTRY</button>
            <button onClick={() => nav("/leaderboard")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-leaderboard">⧉ LEADERBOARD</button>
            <button onClick={() => nav("/regulator")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-regulator">⧉ REGULATOR</button>
          </div>
        </div>
        <div className="mono text-[10px] tracking-widest text-[#808080]">TEST MODE</div>
      </header>

      <main className="flex-1 px-8 py-16">
        <div className="max-w-6xl mx-auto">
          <div className="mono text-[10px] tracking-[0.3em] text-[#00FF41] mb-6">// PRICING SPECIFICATIONS</div>
          <h1 className="sans text-5xl font-light tracking-tight mb-3" data-testid="pricing-heading">
            Deterministic billing. Fixed-precision tiers.
          </h1>
          <div className="mono text-[10px] text-[#808080] tracking-widest mt-6 mb-12">
            THREE TIERS · EUR · VAT ADDED AT CHECKOUT WHERE APPLICABLE
          </div>

          {err && (
            <div className="ae-border-strong px-4 py-3 mono text-xs text-[#FF0000] mb-8" data-testid="pricing-error">
              {err}
            </div>
          )}

          {/* Active subscription banner — only visible when the caller is
              already provisioned on a paid tier. Zero fluff, one command. */}
          {tier?.active && (
            <div className="ae-border-strong mb-10 grid grid-cols-[1fr_auto]" data-testid="pricing-active-banner">
              <div className="px-6 py-5 border-r-[0.5px] border-[#2A2A2A]">
                <div className="mono text-[10px] tracking-widest text-[#00FF41]">// ACTIVE PROVISION</div>
                <div className="mono text-sm text-[#E8E8E8] mt-2">
                  Current tier · <span className="text-[#00FF41]">{tier.plan_id?.toUpperCase().replace("_", " · ") || "—"}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={openPortal}
                disabled={busy !== null}
                data-testid="pricing-manage-btn"
                className="mono text-[11px] tracking-widest px-6 border-l-[0.5px] border-[#00FF41] text-[#00FF41] hover:bg-[#00FF41] hover:text-black disabled:opacity-40"
              >
                {busy === "portal" ? "OPENING PORTAL…" : "▸ MANAGE SUBSCRIPTION"}
              </button>
            </div>
          )}

          {/* Specification grid */}
          <div className="ae-border-strong" data-testid="pricing-grid">
            {/* Header row: tier tag */}
            <div className="grid grid-cols-3 border-b-[0.5px] border-[#2A2A2A]">
              {PLANS.map((p, idx) => (
                <div
                  key={`${p.plan_id}-tag`}
                  className={`px-6 py-4 ${idx < 2 ? "border-r-[0.5px] border-[#2A2A2A]" : ""} ${p.featured ? "bg-[#050505]" : ""}`}
                >
                  <div className="mono text-[10px] tracking-[0.3em]" style={{ color: p.accent }}>{p.tag}</div>
                  {p.featured && (
                    <div className="mono text-[9px] tracking-widest text-[#00FF41] mt-1">▸ ACTIVE</div>
                  )}
                </div>
              ))}
            </div>

            {/* Price row */}
            <div className="grid grid-cols-3 border-b-[0.5px] border-[#2A2A2A]">
              {PLANS.map((p, idx) => (
                <div
                  key={`${p.plan_id}-price`}
                  className={`px-6 py-8 ${idx < 2 ? "border-r-[0.5px] border-[#2A2A2A]" : ""} ${p.featured ? "bg-[#050505]" : ""}`}
                >
                  <div className="flex items-baseline gap-2">
                    <div className="mono text-4xl font-light" style={{ color: p.accent }} data-testid={`pricing-price-${p.plan_id}`}>
                      {p.price}
                    </div>
                    <div className="mono text-[11px] text-[#808080] tracking-wider">{p.cadence}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Feature rows — one per row across tiers, so cells align */}
            {Array.from({ length: MAX_ROWS }).map((_, rowIdx) => (
              <div key={`row-${rowIdx}`} className="grid grid-cols-3 border-b-[0.5px] border-[#2A2A2A]">
                {PLANS.map((p, colIdx) => {
                  const feat = p.features[rowIdx];
                  return (
                    <div
                      key={`${p.plan_id}-${rowIdx}`}
                      data-testid={`pricing-feature-${p.plan_id}-${rowIdx}`}
                      className={`px-6 py-3.5 flex items-center gap-3 ${colIdx < 2 ? "border-r-[0.5px] border-[#2A2A2A]" : ""} ${p.featured ? "bg-[#050505]" : ""}`}
                    >
                      {feat ? (
                        <>
                          <span className="mono text-[10px]" style={{ color: p.accent }}>▸</span>
                          <span className="mono text-[12px] text-[#E8E8E8]">{feat}</span>
                        </>
                      ) : (
                        <span className="mono text-[10px] text-[#333]">—</span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}

            {/* CTA row */}
            <div className="grid grid-cols-3">
              {PLANS.map((p, idx) => {
                const isOwned = tier?.active && tier.plan_id === p.plan_id;
                const isOtherOwned = tier?.active && tier.plan_id !== p.plan_id && p.plan_id !== "enterprise";
                return (
                <div
                  key={`${p.plan_id}-cta`}
                  className={`px-6 py-6 ${idx < 2 ? "border-r-[0.5px] border-[#2A2A2A]" : ""} ${p.featured ? "bg-[#050505]" : ""}`}
                >
                  {p.plan_id === "enterprise" ? (
                    <a
                      href="#contact"
                      onClick={contactEnterprise}
                      data-testid={`pricing-cta-${p.plan_id}`}
                      rel="nofollow noopener"
                      className="block text-center mono text-[11px] tracking-widest py-3 px-4 border-[0.5px] border-[#FFD700] text-[#FFD700] hover:bg-[#FFD700] hover:text-black transition-colors"
                    >
                      {p.cta}
                    </a>
                  ) : isOwned ? (
                    <button
                      type="button"
                      onClick={openPortal}
                      disabled={busy !== null}
                      data-testid={`pricing-cta-${p.plan_id}`}
                      className="w-full mono text-[11px] tracking-widest py-3 px-4 border-[0.5px] border-[#00FF41] text-[#00FF41] hover:bg-[#00FF41] hover:text-black transition-colors disabled:opacity-40"
                    >
                      {busy === "portal" ? "OPENING PORTAL…" : "▸ PROVISIONED · MANAGE"}
                    </button>
                  ) : isOtherOwned ? (
                    <button
                      type="button"
                      onClick={openPortal}
                      disabled={busy !== null}
                      data-testid={`pricing-cta-${p.plan_id}`}
                      className="w-full mono text-[11px] tracking-widest py-3 px-4 border-[0.5px] border-[#808080] text-[#808080] hover:text-white hover:border-white transition-colors disabled:opacity-40"
                    >
                      ▸ SWITCH VIA PORTAL
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => subscribe(p.plan_id)}
                      disabled={busy !== null}
                      data-testid={`pricing-cta-${p.plan_id}`}
                      className={`w-full mono text-[11px] tracking-widest py-3 px-4 border-[0.5px] transition-colors ${
                        p.featured
                          ? "bg-[#00FF41] text-black border-[#00FF41] hover:bg-white hover:border-white"
                          : "border-[#E8E8E8] text-[#E8E8E8] hover:bg-[#E8E8E8] hover:text-black"
                      } disabled:bg-[#333] disabled:text-[#808080] disabled:border-[#333] disabled:cursor-not-allowed`}
                    >
                      {busy === p.plan_id ? "REDIRECTING…" : p.cta}
                    </button>
                  )}
                </div>
                );
              })}
            </div>
          </div>

          {/* Specification bar */}
          <div className="mt-14 ae-border-strong grid grid-cols-4" data-testid="pricing-spec-bar">
            <Cell label="PROCESSOR" value="STRIPE" note="PCI-DSS Level 1 · SCA compliant" />
            <Cell label="TEST CARD" value="4242 …" note="Any future date · any CVC" border />
            <Cell label="CURRENCY" value="EUR" note="VAT calculated at checkout" border />
            <Cell label="CANCELLATION" value="AT ANY TIME" note="Ledger retained · verification permanent" border />
          </div>
        </div>
      </main>

      <footer className="ae-border-strong border-t px-8 py-3 mono text-[10px] text-[#808080] flex justify-between">
        <div>© AUDITENGINE // THE MIRROR OF CERTAINTY</div>
        <div>PRICING SPECIFICATIONS · SECURED BY STRIPE</div>
      </footer>
    </div>
  );
}

function Cell({ label, value, note, border = false }) {
  return (
    <div className={`p-6 ${border ? "border-l-[0.5px] border-[#2A2A2A]" : ""}`}>
      <div className="mono text-[10px] text-[#808080] tracking-widest">{label}</div>
      <div className="mono text-lg text-[#00FF41] mt-3">{value}</div>
      <div className="mono text-[10px] text-[#808080] mt-2 leading-relaxed">{note}</div>
    </div>
  );
}
