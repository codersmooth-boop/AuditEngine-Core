import React from "react";

/** Clinical confirmation dialog — replaces window.confirm().
 *  Renders inline on top of the current page with 0.5px borders, monochrome,
 *  no rounding, no shadow. Destructive action defaults to #FF0000 red.
 */
export default function ConfirmDialog({
  open,
  title = "// CONFIRM ACTION",
  message,
  confirmLabel = "▸ EXECUTE",
  cancelLabel = "← ABORT",
  tone = "#FF0000",
  onConfirm,
  onCancel,
  testid = "confirm-dialog",
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 ae-fade-in"
      data-testid={testid}
      onClick={onCancel}
    >
      <div
        className="ae-border-strong bg-black max-w-md w-[420px] mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="ae-border-strong border-b px-6 py-3">
          <div className="mono text-[10px] tracking-[0.3em]" style={{ color: tone }}>
            {title}
          </div>
        </div>
        <div className="p-6">
          <p className="sans text-base leading-relaxed text-[#E8E8E8]" data-testid={`${testid}-message`}>
            {message}
          </p>
        </div>
        <div className="ae-border-strong border-t grid grid-cols-2 gap-0">
          <button
            type="button"
            onClick={onCancel}
            data-testid={`${testid}-cancel`}
            className="mono text-[11px] tracking-widest py-4 text-[#808080] hover:text-white border-r-[0.5px] border-[#2A2A2A]"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            data-testid={`${testid}-confirm`}
            className="mono text-[11px] tracking-widest py-4 hover:bg-white hover:text-black transition-colors"
            style={{ color: tone }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
