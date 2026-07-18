import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL;
const MAX_POLLS = 8;
const POLL_INTERVAL_MS = 2000;

export default function PaymentSuccess() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const [status, setStatus] = useState("polling");
  const [detail, setDetail] = useState(null);
  const [tries, setTries] = useState(0);

  useEffect(() => {
    if (!sessionId) {
      setStatus("missing");
      return;
    }
    let cancelled = false;
    let attempts = 0;

    async function poll() {
      if (cancelled) return;
      attempts += 1;
      setTries(attempts);
      try {
        const res = await fetch(`${API}/api/payments/status/${sessionId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setDetail(data);
        if (data.payment_status === "paid") {
          setStatus("paid");
          return;
        }
        if (["failed", "expired", "refunded"].includes(data.payment_status)) {
          setStatus(data.payment_status);
          return;
        }
      } catch (e) {
        setDetail({ error: String(e) });
      }
      if (attempts >= MAX_POLLS) {
        setStatus("timeout");
        return;
      }
      setTimeout(poll, POLL_INTERVAL_MS);
    }

    poll();
    return () => { cancelled = true; };
  }, [sessionId]);

  const banner = {
    polling: { text: "PROVISIONING…", color: "#FFBF00" },
    paid: { text: "PROVISIONING COMPLETE", color: "#00FF41" },
    failed: { text: "PROVISIONING FAILED", color: "#FF0000" },
    expired: { text: "SESSION EXPIRED", color: "#FF0000" },
    refunded: { text: "REFUNDED", color: "#FFBF00" },
    timeout: { text: "PENDING · WEBHOOK RETRY", color: "#FFBF00" },
    missing: { text: "MISSING SESSION_ID", color: "#FF0000" },
  }[status];

  return (
    <div className="min-h-screen bg-black text-[#E8E8E8] flex flex-col">
      <header className="ae-border-strong border-b px-8 py-4">
        <div className="mono text-xs tracking-[0.2em]">AUDITENGINE // PAYMENT RECEIPT</div>
      </header>

      <main className="flex-1 flex items-center justify-center px-8 py-16">
        <div className="w-full max-w-3xl">
          <div className="mono text-[10px] tracking-[0.3em] mb-6" style={{ color: banner.color }} data-testid="payment-status-banner">
            // {banner.text}
          </div>
          <h1 className="sans text-4xl font-light tracking-tight mb-3" data-testid="payment-success-heading">
            {status === "paid" ? "Access provisioned." : status === "polling" ? "Sealing the transaction." : "Transaction record."}
          </h1>
          <p className="sans text-[#808080] text-base leading-relaxed mb-10 max-w-2xl">
            {status === "paid"
              ? "Your subscription is active. AuditEngine is now provisioned under this workspace. Every subsequent audit will be signed and folded into your Merkle Root ledger."
              : status === "polling"
              ? `Awaiting confirmation from Stripe · poll ${tries}/${MAX_POLLS}. Webhook fallback and direct Stripe check run in parallel.`
              : "Details below. If you believe this is in error, please contact support with the session ID."}
          </p>

          <div className="ae-border-strong">
            <div className="ae-border-strong border-b px-6 py-3">
              <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// RECEIPT</div>
            </div>
            <div className="p-6 grid grid-cols-[160px_1fr] gap-y-3 gap-x-6 mono text-xs">
              <div className="text-[#808080]">SESSION_ID</div>
              <div className="text-[#E8E8E8] break-all" data-testid="payment-session-id">{sessionId || "—"}</div>
              <div className="text-[#808080]">STATUS</div>
              <div style={{ color: banner.color }} data-testid="payment-status-value">{status.toUpperCase()}</div>
              {detail?.payment_status && (
                <>
                  <div className="text-[#808080]">PAYMENT_STATUS</div>
                  <div className="text-[#E8E8E8]">{detail.payment_status}</div>
                </>
              )}
              {detail?.error && (
                <>
                  <div className="text-[#808080]">ERROR</div>
                  <div className="text-[#FF0000]">{detail.error}</div>
                </>
              )}
            </div>
          </div>

          <div className="mt-10 flex gap-4">
            <button
              onClick={() => nav("/dashboard")}
              data-testid="payment-continue-btn"
              className="mono text-[11px] tracking-widest px-6 py-3 border-[0.5px] border-[#00FF41] text-[#00FF41] hover:bg-[#00FF41] hover:text-black"
            >
              ▸ PROCEED TO WORKSPACE
            </button>
            <button
              onClick={() => nav("/pricing")}
              className="mono text-[11px] tracking-widest px-6 py-3 border-[0.5px] border-[#2A2A2A] text-[#808080] hover:text-white hover:border-white"
            >
              ← BACK TO PRICING
            </button>
          </div>
        </div>
      </main>

      <footer className="ae-border-strong border-t px-8 py-3 mono text-[10px] text-[#808080] flex justify-between">
        <div>© AUDITENGINE // THE MIRROR OF CERTAINTY</div>
        <div>PAYMENT PROCESSING · STRIPE</div>
      </footer>
    </div>
  );
}
