import React from "react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function Login() {
  const login = () => {
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8] flex flex-col">
      <header className="ae-border-strong border-b flex items-center justify-between px-8 py-4">
        <div className="mono text-xs tracking-[0.2em] text-[#E8E8E8]">AUDITENGINE // v1.0</div>
        <div className="mono text-xs text-[#808080]">SECURE TERMINAL</div>
      </header>

      <main className="flex-1 grid grid-cols-1 lg:grid-cols-2">
        <section className="relative border-r-[0.5px] border-[#1A1A1A] p-16 flex flex-col justify-between ae-grid-noise">
          <div className="relative z-10">
            <div className="mono text-[10px] tracking-[0.3em] text-[#808080] mb-8">// THE MIRROR OF CERTAINTY</div>
            <h1 className="sans font-light text-6xl leading-[1.05] mb-10 tracking-tight">
              High-precision<br />
              ESG compliance<br />
              intelligence.
            </h1>
            <p className="sans text-[#808080] text-base max-w-md leading-relaxed">
              A clinical instrument for auditors, CFOs and sustainability officers.
              CSRD · ESRS · EU Taxonomy · CSDDD · SFDR — quantified.
            </p>
          </div>
          <div className="relative z-10 mono text-[10px] text-[#808080] tracking-widest">
            <div>OPERATIONAL ENERGY · SUPPLY CHAIN · HUMAN &amp; SOCIAL · CONTEXT LAYER</div>
          </div>
        </section>

        <section className="p-16 flex flex-col justify-center max-w-2xl">
          <div className="mono text-[10px] tracking-[0.3em] text-[#00FF41] mb-6">// AUTHENTICATE</div>
          <h2 className="sans text-3xl mb-3 font-light">Enter the audit terminal.</h2>
          <p className="mono text-xs text-[#808080] mb-10 leading-relaxed">
            Access is restricted to verified operators. Sessions expire after 7 days.
          </p>

          <button
            data-testid="login-google-btn"
            onClick={login}
            className="mono text-xs tracking-[0.2em] ae-border-strong px-8 py-4 bg-black text-[#E8E8E8] hover:bg-[#0D0D0D] hover:text-white transition-colors flex items-center justify-between"
          >
            <span>AUTHENTICATE VIA GOOGLE</span>
            <span className="text-[#00FF41]">→</span>
          </button>

          <div className="mt-16 grid grid-cols-2 gap-0 ae-border-strong">
            {[
              ["ISO 27001", "AUDIT-GRADE"],
              ["CSRD", "COMPLIANT ENGINE"],
              ["ESRS", "FULL COVERAGE"],
              ["EU TAX.", "ART. 8 KPIs"],
            ].map(([k, v], i) => (
              <div key={i} className={`p-4 ${i % 2 === 0 ? "border-r-[0.5px]" : ""} ${i < 2 ? "border-b-[0.5px]" : ""} border-[#2A2A2A]`}>
                <div className="mono text-[10px] text-[#808080] tracking-widest">{k}</div>
                <div className="mono text-xs mt-1 text-[#E8E8E8]">{v}</div>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="ae-border-strong border-t px-8 py-3 mono text-[10px] text-[#808080] flex justify-between">
        <div>© AUDITENGINE</div>
        <div className="flex items-center gap-6">
          <a href="/verify" data-testid="public-verify-link" className="text-[#808080] hover:text-[#00FF41]">⧉ PUBLIC VERIFY</a>
          <a href="/registry" data-testid="public-registry-link" className="text-[#808080] hover:text-[#00FF41]">⧉ GLOBAL ROOT REGISTRY</a>
          <a href="/leaderboard" data-testid="public-leaderboard-link" className="text-[#808080] hover:text-[#00FF41]">⧉ LEADERBOARD</a>
          <div>SYSTEM STATUS: <span className="text-[#00FF41]">OPERATIONAL</span></div>
        </div>
      </footer>
    </div>
  );
}
