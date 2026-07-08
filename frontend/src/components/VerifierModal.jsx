import React, { useState } from "react";

async function sha256Hex(text) {
  const buf = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, "0")).join("");
}

export default function VerifierModal({ audit, expectedHash, onClose }) {
  const [status, setStatus] = useState(null); // null | "MATCH" | "TAMPER" | "ERROR"
  const [logHash, setLogHash] = useState("");
  const [declared, setDeclared] = useState("");
  const [filename, setFilename] = useState("");

  const onFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFilename(f.name);
    try {
      const text = await f.text();
      // Extract declared composite from the .log header
      const m = text.match(/composite\s*=\s*([a-f0-9]{64})/i);
      const declaredHash = m ? m[1] : "";
      setDeclared(declaredHash);
      // Also hash the raw file content itself as a supplemental integrity signal
      const fileHash = await sha256Hex(text);
      setLogHash(fileHash);
      if (declaredHash && expectedHash && declaredHash.toLowerCase() === expectedHash.toLowerCase()) {
        setStatus("MATCH");
      } else {
        setStatus("TAMPER");
      }
    } catch (e) {
      setStatus("ERROR");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" data-testid="verifier-modal">
      <div className="absolute inset-0 bg-black/80" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-black ae-border-strong">
        <div className="ae-border-strong border-b p-6 flex items-center justify-between">
          <div>
            <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// FINGERPRINT VERIFIER</div>
            <h2 className="sans text-2xl mt-1 font-light">Truth-check the evidence chain.</h2>
          </div>
          <button data-testid="verifier-close" onClick={onClose} className="mono text-xs text-[#808080] hover:text-[#FF0000]">CLOSE ✕</button>
        </div>
        <div className="p-6 space-y-6">
          <div>
            <div className="mono text-[10px] text-[#808080] tracking-widest">EXPECTED COMPOSITE HASH</div>
            <div className="mono text-xs text-[#00FF41] break-all mt-2">{expectedHash || "—"}</div>
            <div className="mono text-[10px] text-[#808080] mt-1">Audit: {audit.audit_id} · {audit.client_name}</div>
          </div>

          <label className="block ae-border-strong p-8 text-center cursor-pointer hover:bg-[#0D0D0D]">
            <input data-testid="verifier-file-input" type="file" accept=".log,.txt" hidden onChange={onFile} />
            <div className="mono text-[10px] tracking-[0.3em] text-[#808080] mb-3">// UPLOAD .LOG</div>
            <div className="sans text-lg text-[#E8E8E8]">Drop or click to upload signed .log</div>
            {filename && <div className="mono text-[10px] text-[#00FF41] mt-3">Loaded: {filename}</div>}
          </label>

          {status === "MATCH" && (
            <div className="ae-border-strong p-6" data-testid="verifier-match">
              <div className="mono text-2xl text-[#00FF41] tracking-widest">[MATCH VERIFIED]</div>
              <div className="mono text-xs text-[#E8E8E8] mt-3">The uploaded log's declared composite hash matches the audit's evidence chain.</div>
              <div className="mono text-[10px] text-[#808080] mt-2 break-all">declared = {declared}</div>
              <div className="mono text-[10px] text-[#808080] break-all">file_sha256 = {logHash}</div>
            </div>
          )}
          {status === "TAMPER" && (
            <div className="ae-border-strong p-6" data-testid="verifier-tamper">
              <div className="mono text-2xl text-[#FF0000] tracking-widest">[TAMPER DETECTED]</div>
              <div className="mono text-xs text-[#E8E8E8] mt-3">The uploaded log does not carry the expected composite hash. Chain-of-custody is broken.</div>
              <div className="mono text-[10px] text-[#808080] mt-2 break-all">declared = {declared || "(none found)"}</div>
              <div className="mono text-[10px] text-[#808080] break-all">expected = {expectedHash}</div>
              <div className="mono text-[10px] text-[#808080] break-all">file_sha256 = {logHash}</div>
            </div>
          )}
          {status === "ERROR" && (
            <div className="mono text-xs text-[#FF0000]">! Failed to read file.</div>
          )}
        </div>
      </div>
    </div>
  );
}
