import React, { useEffect, useMemo, useState } from "react";
import { searchNace, createAudit } from "../lib/api";

export default function NewAuditDrawer({ open, onClose, onCreated }) {
  const [clientName, setClientName] = useState("");
  const [year, setYear] = useState(new Date().getUTCFullYear() - 1);
  const [query, setQuery] = useState("");
  const [naceResults, setNaceResults] = useState([]);
  const [selectedNace, setSelectedNace] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    let cancel = false;
    (async () => {
      const r = await searchNace(query);
      if (!cancel) setNaceResults(r);
    })();
    return () => { cancel = true; };
  }, [query, open]);

  useEffect(() => {
    if (!open) {
      setClientName(""); setYear(new Date().getUTCFullYear() - 1);
      setQuery(""); setSelectedNace(null); setError("");
    }
  }, [open]);

  const canSubmit = useMemo(
    () => clientName.trim().length >= 2 && selectedNace && year >= 2000 && year <= 2100,
    [clientName, selectedNace, year]
  );

  const submit = async (e) => {
    e.preventDefault();
    if (!canSubmit || submitting) return;
    setSubmitting(true); setError("");
    try {
      const a = await createAudit({
        client_name: clientName.trim(),
        nace_code: selectedNace.code || selectedNace.section,
        nace_name: selectedNace.name,
        reporting_year: Number(year),
      });
      onCreated(a);
    } catch (err) {
      setError(err?.response?.data?.detail || "Creation failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="new-audit-drawer">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative w-full max-w-xl bg-black ae-border-strong border-l h-full overflow-y-auto ae-slide-up">
        <div className="ae-border-strong border-b p-6 flex items-center justify-between">
          <div>
            <div className="mono text-[10px] text-[#808080] tracking-widest">// NEW AUDIT</div>
            <h2 className="sans text-2xl mt-1 font-light">Initialize audit case.</h2>
          </div>
          <button data-testid="close-drawer-btn" onClick={onClose} className="mono text-xs text-[#808080] hover:text-[#FF0000]">CLOSE ✕</button>
        </div>

        <form onSubmit={submit} className="p-6 space-y-8">
          <div>
            <label className="mono text-[10px] text-[#808080] tracking-widest">CLIENT NAME</label>
            <input
              data-testid="client-name-input"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              placeholder="ACME Industries S.A."
              className="mt-2 w-full bg-[#050505] ae-border-strong px-4 py-3 mono text-sm text-[#E8E8E8] focus:outline-none focus:border-[#00FF41]"
            />
          </div>

          <div>
            <label className="mono text-[10px] text-[#808080] tracking-widest">NACE REV. 2 CODE</label>
            <input
              data-testid="nace-search-input"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setSelectedNace(null); }}
              placeholder="Search 996 codes — e.g. 'manufacture of cement'"
              className="mt-2 w-full bg-[#050505] ae-border-strong px-4 py-3 mono text-sm text-[#E8E8E8] focus:outline-none focus:border-[#00FF41]"
            />
            {selectedNace ? (
              <div className="mt-2 ae-border-strong px-4 py-3 bg-[#0D0D0D] flex items-center justify-between" data-testid="nace-selected">
                <div>
                  <div className="mono text-xs text-[#00FF41]">{selectedNace.section} · {selectedNace.code || "—"}</div>
                  <div className="sans text-sm mt-1">{selectedNace.name}</div>
                </div>
                <button type="button" onClick={() => setSelectedNace(null)} className="mono text-[10px] text-[#808080] hover:text-[#FF0000]">CLEAR</button>
              </div>
            ) : (
              <div className="mt-2 ae-border max-h-64 overflow-y-auto">
                {naceResults.map((n, idx) => (
                  <button
                    key={`${n.section}-${n.code}-${idx}`}
                    type="button"
                    data-testid={`nace-option-${idx}`}
                    onClick={() => setSelectedNace(n)}
                    className="w-full text-left px-4 py-2 hover:bg-[#0D0D0D] border-b-[0.5px] border-[#1A1A1A] flex items-center gap-4"
                  >
                    <span className="mono text-[10px] text-[#00FF41] w-16 shrink-0">{n.section}·{n.code || "—"}</span>
                    <span className="sans text-xs text-[#E8E8E8] truncate">{n.name}</span>
                    <span className="mono text-[10px] text-[#808080] ml-auto">L{n.level}</span>
                  </button>
                ))}
                {naceResults.length === 0 && (
                  <div className="mono text-xs text-[#808080] p-4">No matches.</div>
                )}
              </div>
            )}
          </div>

          <div>
            <label className="mono text-[10px] text-[#808080] tracking-widest">REPORTING YEAR</label>
            <input
              data-testid="year-input"
              type="number" min="2000" max="2100"
              value={year} onChange={(e) => setYear(e.target.value)}
              className="mt-2 w-full bg-[#050505] ae-border-strong px-4 py-3 mono text-sm text-[#E8E8E8] focus:outline-none focus:border-[#00FF41]"
            />
          </div>

          {error && <div className="mono text-xs text-[#FF0000]" data-testid="drawer-error">! {error}</div>}

          <div className="pt-4 ae-border-strong border-t flex justify-end gap-3">
            <button type="button" onClick={onClose} className="mono text-xs tracking-widest px-6 py-3 ae-border-strong hover:bg-[#0D0D0D]">CANCEL</button>
            <button
              type="submit"
              data-testid="create-audit-submit"
              disabled={!canSubmit || submitting}
              className={`mono text-xs tracking-widest px-6 py-3 ae-border-strong ${canSubmit ? "bg-[#00FF41] text-black hover:bg-white" : "bg-[#0D0D0D] text-[#808080] cursor-not-allowed"}`}
            >
              {submitting ? "INITIALIZING..." : "→ INITIALIZE"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
