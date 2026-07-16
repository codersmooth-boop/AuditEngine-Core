import React from "react";
import { useNavigate } from "react-router-dom";

export default function PaymentCancel() {
  const nav = useNavigate();
  return (
    <div className="min-h-screen bg-black text-[#E8E8E8] flex flex-col">
      <header className="ae-border-strong border-b px-8 py-4">
        <div className="mono text-xs tracking-[0.2em]">AUDITENGINE // PAYMENT ABORTED</div>
      </header>
      <main className="flex-1 flex items-center justify-center px-8 py-16">
        <div className="w-full max-w-2xl">
          <div className="mono text-[10px] tracking-[0.3em] text-[#FFBF00] mb-6" data-testid="payment-cancel-banner">
            // CHECKOUT CANCELLED
          </div>
          <h1 className="sans text-4xl font-light tracking-tight mb-3" data-testid="payment-cancel-heading">
            No transaction recorded.
          </h1>
          <p className="sans text-[#808080] text-base leading-relaxed mb-10 max-w-xl">
            You closed the Stripe checkout before completing payment. Nothing was charged.
            Your session was released and no receipt was minted.
          </p>
          <div className="flex gap-4">
            <button
              onClick={() => nav("/pricing")}
              data-testid="payment-cancel-retry-btn"
              className="mono text-[11px] tracking-widest px-6 py-3 border-[0.5px] border-[#00FF41] text-[#00FF41] hover:bg-[#00FF41] hover:text-black"
            >
              ▸ RETURN TO PRICING
            </button>
            <button
              onClick={() => nav("/")}
              className="mono text-[11px] tracking-widest px-6 py-3 border-[0.5px] border-[#2A2A2A] text-[#808080] hover:text-white hover:border-white"
            >
              ← HOME
            </button>
          </div>
        </div>
      </main>
      <footer className="ae-border-strong border-t px-8 py-3 mono text-[10px] text-[#808080] flex justify-between">
        <div>© AUDITENGINE // THE MIRROR OF CERTAINTY</div>
        <div>NO CHARGE INCURRED</div>
      </footer>
    </div>
  );
}
