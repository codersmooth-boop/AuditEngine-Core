import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getBillingTier, createPortalSession } from "../lib/api";

/** Header command link — free users see "PROVISION ACCESS", paid users see
 *  "MANAGE SUBSCRIPTION". Clicking the paid variant opens the Stripe Billing
 *  Portal for the current customer.
 */
export default function ProvisionAccessLink() {
  const nav = useNavigate();
  const [tier, setTier] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const t = await getBillingTier();
        if (!cancelled) setTier(t);
      } catch {
        if (!cancelled) setTier({ active: false, tier: "free" });
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function onClick() {
    if (busy) return;
    if (tier?.active) {
      setBusy(true);
      try {
        const { portal_url } = await createPortalSession(window.location.href);
        window.location.href = portal_url;
      } catch (e) {
        setBusy(false);
        // fall back to pricing so the user is never stuck
        nav("/pricing");
      }
    } else {
      nav("/pricing");
    }
  }

  const paid = !!tier?.active;
  const label = tier == null
    ? "// LOADING…"
    : paid ? "▸ MANAGE SUBSCRIPTION" : "▸ PROVISION ACCESS";
  const testId = paid ? "manage-subscription-link" : "provision-access-link";
  const color = paid ? "#00FF41" : "#E8E8E8";

  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      disabled={busy || tier == null}
      className="mono text-[10px] tracking-widest px-3 py-2 border-[0.5px] hover:bg-[#0D0D0D] disabled:opacity-40"
      style={{ borderColor: color, color }}
    >
      {busy ? "OPENING PORTAL…" : label}
    </button>
  );
}
