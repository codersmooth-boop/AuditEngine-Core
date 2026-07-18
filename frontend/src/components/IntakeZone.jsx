import React, { useRef, useState } from "react";
import { uploadFiles } from "../lib/api";

const ACCEPTED = [".pdf", ".xlsx", ".xls", ".txt", ".csv"];
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;  // 25 MB · matches server ceiling

const fmtMB = (b) => `${(b / (1024 * 1024)).toFixed(1)} MB`;

export default function IntakeZone({ auditId, onUploaded, disabled }) {
  const [hover, setHover] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [names, setNames] = useState([]);
  const [error, setError] = useState("");
  const ref = useRef();

  const validate = (files) => files.filter(f => ACCEPTED.some(ext => f.name.toLowerCase().endsWith(ext)));

  const doUpload = async (fs) => {
    const clean = validate(fs);
    if (clean.length === 0) {
      setError("Only PDF, XLSX, XLS, TXT, CSV files accepted.");
      return;
    }
    const oversized = clean.find(f => f.size > MAX_UPLOAD_BYTES);
    if (oversized) {
      setError(`File exceeds 25 MB ceiling: ${oversized.name} (${fmtMB(oversized.size)})`);
      return;
    }
    setError(""); setUploading(true); setNames(clean.map(f => f.name));
    try {
      await uploadFiles(auditId, clean);
      onUploaded?.();
    } catch (e) {
      setError(e?.response?.data?.detail || "Upload failed");
      setUploading(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault(); setHover(false);
    if (disabled || uploading) return;
    doUpload(Array.from(e.dataTransfer.files));
  };

  const onPick = (e) => {
    if (disabled || uploading) return;
    doUpload(Array.from(e.target.files));
  };

  if (uploading) {
    return (
      <div data-testid="intake-status-bar" className="ae-border-strong h-8 flex items-center px-4 bg-black">
        <span className="w-2 h-2 bg-[#00FF41] ae-pulse mr-3" />
        <span className="mono text-[10px] tracking-[0.3em] text-[#E8E8E8]">RECEIVING INPUT</span>
        <span className="mono text-[10px] text-[#808080] ml-6 truncate">{names.join(" · ")}</span>
      </div>
    );
  }

  return (
    <div
      data-testid="intake-zone"
      onDragOver={(e) => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={onDrop}
      onClick={() => ref.current?.click()}
      className={`ae-border-strong cursor-pointer p-16 text-center transition-colors ${hover ? "bg-[#0D0D0D] border-[#00FF41]" : "bg-black"}`}
    >
      <input ref={ref} type="file" multiple accept=".pdf,.xlsx,.xls,.txt,.csv" hidden onChange={onPick} data-testid="file-input" />
      <div className="mono text-[10px] tracking-[0.3em] text-[#808080] mb-6">// THE BLACK BOX INTAKE</div>
      <div className="sans text-3xl font-light text-[#E8E8E8] mb-3">Drop source documents.</div>
      <div className="mono text-xs text-[#808080]">PDF · XLSX · TXT · CSV · Multi-file supported · 25 MB / file</div>
      <div className="mono text-[10px] text-[#00FF41] mt-8 ae-cursor">DRAG OR CLICK TO SELECT</div>
      {error && <div className="mono text-xs text-[#FF0000] mt-6" data-testid="intake-error">! {error}</div>}
    </div>
  );
}
