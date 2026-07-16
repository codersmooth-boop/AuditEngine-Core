import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL;

// Obfuscated Enterprise contact — assembled at click time so it never appears
// as a scrapeable literal in the served HTML/JS.
const ENT_LOCAL = [99, 111, 100, 101, 114, 115, 109, 111, 111, 116, 104]; // "codersmooth"
const ENT_DOMAIN = [103, 109, 97, 105, 108, 46, 99, 111, 109];             // "gmail.com"

function assembleEnterpriseHref() {
  const local = String.fromCharCode(...ENT_LOCAL);
  const domain = String.fromCharCode(...ENT_DOMAIN);
  const subject = encodeURIComponent("AuditEngine · Enterprise Inquiry");
  const body = encodeURIComponent(
    "Hello,\n\nWe are evaluating AuditEngine for institutional deployment.\n\nOrganization:\nExpected audit volume / year:\nDeployment model (SaaS / VPC / On-prem):\n\nBest,",
  );
  return `mailto:${local}\u0040${domain}?subject=${subject}&body=${body}`;
}

const PLANS = [
  {
    key: "professional_monthly",
    tag: "// PROFESSIONAL",
    price: "€49",
    cadence: "/ month",
    tagline: "The standard operating instrument.",
    features: [
      "Unlimited ESG audits",
      "Board Brief + Full Audit PDF",
      "Merkle-Root snapshots · immutable trail",
      "Trust Anchor microsite",
      "Regulator Sandbox access",
      "Public attestation badges",
    ],
    cta: "▸ SUBSCRIBE MONTHLY",
    accent: "#E8E8E8",
  },
  {
    key: "annual_yearly",
    tag: "// ANNUAL",
    price: "€490",
    cadence: "/ year",
    tagline: "Two months on the house. Same instrument.",
    features: [
      "Everything in Professional",
      "Priority audit throughput",
      "Trust Streak locked · gold ledger",
      "Dedicated onboarding call",
      "Signed policy attestation letter",
      "2 months free vs monthly",
    ],
    cta: "▸ SUBSCRIBE ANNUALLY",
    accent: "#00FF41",
    featured: true,
  },
  {
    key: "enterprise",
    tag: "// ENTERPRISE",
    price: "Bespoke",
    cadence: "· quoted",
    tagline: "For supervisory bodies and multi-jurisdiction estates.",
    features: [
      "Everything in Annual",
      "VPC / On-prem deployment",
      "Custom regulatory taxonomies",
      "Volume-priced Regulator keys",
      "SLA + named auditor liaison",
      "White-label registry mirror",
    ],
    cta: "▸ CONTACT FOR QUOTE",
    accent: "#FFD700",
  },
];

export default function Pricing() {
  const nav = useNavigate();
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState("");

  async function subscribe(lookupKey) {
    setBusy(lookupKey);
    setErr("");
    try {
      const res = await fetch(`${API}/api/payments/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lookup_key: lookupKey,
          origin_url: window.location.origin,
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

  function contactEnterprise(e) {
    e.preventDefault();
    // Assemble the mailto only on user interaction — never in the DOM.
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
            AUDITENGINE // PRICING
          </button>
          <div className="flex gap-6">
            <button onClick={() => nav("/verify")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-verify">⧉ VERIFY ROOT</button>
            <button onClick={() => nav("/registry")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-registry">⧉ REGISTRY</button>
            <button onClick={() => nav("/leaderboard")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-leaderboard">⧉ LEADERBOARD</button>
            <button onClick={() => nav("/regulator")} className="mono text-[10px] tracking-widest text-[#808080] hover:text-white" data-testid="nav-regulator">⧉ REGULATOR</button>
          </div>
        </div>
        <div className="mono text-[10px] tracking-widest text-[#808080]">TEST MODE · STRIPE SANDBOX</div>
      </header>

      <main className="flex-1 px-8 py-16">
        <div className="max-w-6xl mx-auto">
          <div className="mono text-[10px] tracking-[0.3em] text-[#00FF41] mb-6">// PRICING</div>
          <h1 className="sans text-5xl font-light tracking-tight mb-3" data-testid="pricing-heading">
            One instrument. Three engagement tiers.
          </h1>
          <p className="sans text-[#808080] text-base max-w-3xl leading-relaxed mb-14">
            AuditEngine is priced on time, not seats. Every plan ships with the same core precision —
            unlimited audits, cryptographic attestation, and Trust Anchor microsite. The tiers differ
            only in cadence, prestige, and institutional depth.
          </p>

          {err && (
            <div className="ae-border-strong px-4 py-3 mono text-xs text-[#FF0000] mb-8" data-testid="pricing-error">
              {err}
            </div>
          )}

          <div className="grid grid-cols-3 gap-0 ae-border-strong" data-testid="pricing-grid">
            {PLANS.map((p, idx) => (
              <div
                key={p.key}
                data-testid={`pricing-card-${p.key}`}
                className={`p-10 flex flex-col ${idx < 2 ? "border-r-[0.5px] border-[#2A2A2A]" : ""} ${p.featured ? "bg-[#050505]" : ""}`}
              >
                <div className="mono text-[10px] tracking-[0.3em]" style={{ color: p.accent }}>{p.tag}</div>
                {p.featured && (
                  <div className="mono text-[9px] tracking-widest text-[#00FF41] mt-2">▸ ACTIVE · RECOMMENDED</div>
                )}
                <div className="mt-6 flex items-baseline gap-2">
                  <div className="sans text-5xl font-light" data-testid={`pricing-price-${p.key}`}>{p.price}</div>
                  <div className="mono text-[11px] text-[#808080] tracking-wider">{p.cadence}</div>
                </div>
                <p className="sans text-sm text-[#E8E8E8] mt-4 leading-relaxed min-h-[42px]">{p.tagline}</p>

                <ul className="mt-8 space-y-3 flex-1">
                  {p.features.map((f) => (
                    <li key={f} className="mono text-[11px] text-[#E8E8E8] flex gap-3">
                      <span style={{ color: p.accent }}>▸</span>
                      <span className="sans text-[13px]">{f}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-10 pt-6 border-t-[0.5px] border-[#2A2A2A]">
                  {p.key === "enterprise" ? (
                    <a
                      href="#contact"
                      onClick={contactEnterprise}
                      data-testid={`pricing-cta-${p.key}`}
                      rel="nofollow noopener"
                      className="block text-center mono text-[11px] tracking-widest py-3 px-4 border-[0.5px] border-[#FFD700] text-[#FFD700] hover:bg-[#FFD700] hover:text-black transition-colors"
                    >
                      {p.cta}
                    </a>
                  ) : (
                    <button
                      type="button"
                      onClick={() => subscribe(p.key)}
                      disabled={busy !== null}
                      data-testid={`pricing-cta-${p.key}`}
                      className={`w-full mono text-[11px] tracking-widest py-3 px-4 border-[0.5px] transition-colors ${
                        p.featured
                          ? "bg-[#00FF41] text-black border-[#00FF41] hover:bg-white hover:border-white"
                          : "border-[#E8E8E8] text-[#E8E8E8] hover:bg-[#E8E8E8] hover:text-black"
                      } disabled:bg-[#333] disabled:text-[#808080] disabled:border-[#333] disabled:cursor-not-allowed`}
                    >
                      {busy === p.key ? "REDIRECTING…" : p.cta}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Trust bar */}
          <div className="mt-14 ae-border-strong grid grid-cols-4 gap-0" data-testid="pricing-trust-bar">
            <Cell label="PROCESSING" value="STRIPE" note="PCI-DSS Level 1 · SCA compliant" />
            <Cell label="TEST CARD" value="4242 …" note="Any future date · any CVC" border />
            <Cell label="TAX MODE" value="STRIPE-MANAGED" note="VAT calculation, collection and remittance handled." border />
            <Cell label="CANCELLATION" value="AT ANY TIME" note="Ledger integrity is preserved permanently." border />
          </div>

          <div className="mono text-[10px] text-[#808080] leading-relaxed max-w-3xl mt-14">
            The AuditEngine ledger — Merkle Roots, snapshots, and Trust Anchor microsite — remains
            immutable and publicly verifiable regardless of subscription state.
            Verification never expires.
          </div>
        </div>
      </main>

      <footer className="ae-border-strong border-t px-8 py-3 mono text-[10px] text-[#808080] flex justify-between">
        <div>© AUDITENGINE // THE MIRROR OF CERTAINTY</div>
        <div>PRICED IN EUR · VAT ADDED AT CHECKOUT WHERE APPLICABLE</div>
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
