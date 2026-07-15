import React, { useMemo, useState } from "react";

async function sha256Hex(buf) {
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, "0")).join("");
}

async function sha256Text(text) {
  return sha256Hex(new TextEncoder().encode(text));
}

/**
 * Client-side, browser-only reproduction of the AuditEngine hashing protocol.
 * Deterministic algorithm — no server round-trip. Never uploads files anywhere.
 *
 * Protocol (single-audit workspace):
 *   file_hash_i     = SHA-256(file_bytes_i)
 *   composite       = SHA-256(  "|".join(file_hash_i for i in insertion_order) )
 *   merkle_root_1   = SHA-256(  composite )                                  ← for audit_count == 1
 *
 * For multi-audit snapshots, add each audit as a group; merkle_root_N = SHA-256("|".join(composites))
 */
export default function ReproductionTest({ expectedRoot }) {
  const [groups, setGroups] = useState([{ id: 1, files: [], hashes: [], composite: "" }]);
  const [merkle, setMerkle] = useState("");
  const [busy, setBusy] = useState(false);

  const targetRoot = (expectedRoot || "").trim().toLowerCase();

  const onFiles = async (gid, fileList) => {
    if (!fileList || fileList.length === 0) return;
    setBusy(true);
    try {
      const files = Array.from(fileList);
      const hashes = [];
      for (const f of files) {
        const buf = await f.arrayBuffer();
        hashes.push({ name: f.name, size: f.size, sha256: await sha256Hex(buf) });
      }
      const composite = await sha256Text(hashes.map(h => h.sha256).join("|"));
      const next = groups.map(g => g.id === gid ? { ...g, files: files.map(f => ({ name: f.name, size: f.size })), hashes, composite } : g);
      const composites = next.map(g => g.composite).filter(Boolean);
      const root = composites.length ? await sha256Text(composites.join("|")) : "";
      setGroups(next);
      setMerkle(root);
    } finally { setBusy(false); }
  };

  const addGroup = () => setGroups(g => [...g, { id: (g[g.length - 1]?.id || 0) + 1, files: [], hashes: [], composite: "" }]);

  const removeGroup = async (gid) => {
    const next = groups.filter(g => g.id !== gid);
    setGroups(next.length ? next : [{ id: 1, files: [], hashes: [], composite: "" }]);
    const composites = next.map(g => g.composite).filter(Boolean);
    setMerkle(composites.length ? await sha256Text(composites.join("|")) : "");
  };

  const result = useMemo(() => {
    if (!targetRoot || !merkle) return null;
    return merkle === targetRoot ? "MATCH" : "MISMATCH";
  }, [merkle, targetRoot]);

  const totalFiles = groups.reduce((s, g) => s + g.hashes.length, 0);

  return (
    <div className="ae-border-strong" data-testid="reproduction-test">
      <div className="ae-border-strong border-b px-6 py-4 flex items-center justify-between">
        <div>
          <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// SIGNED REPRODUCTION TEST</div>
          <div className="sans text-lg font-light text-[#E8E8E8] mt-1">Recompute the truth in your browser.</div>
        </div>
        <div className="mono text-[10px] text-[#808080] tracking-widest">CLIENT-SIDE · ZERO UPLOAD</div>
      </div>

      <div className="px-6 py-4 mono text-[10px] text-[#808080] leading-relaxed border-b-[0.5px] border-[#1A1A1A]">
        Files are hashed in your browser via <span className="text-[#E8E8E8]">crypto.subtle.digest("SHA-256")</span>. Nothing is transmitted.
        The claimed Merkle root above is the target; your independently-computed root is compared byte-for-byte.
        Single-audit workspaces: drop all evidence files in group #1. Multi-audit workspaces: add one group per audit (insertion order matters).
      </div>

      {groups.map((g, idx) => (
        <div key={g.id} className="px-6 py-5 border-b-[0.5px] border-[#1A1A1A]" data-testid={`repro-group-${g.id}`}>
          <div className="flex items-center justify-between mb-3">
            <div className="mono text-[10px] tracking-widest text-[#808080]">// AUDIT GROUP {String(idx + 1).padStart(2, "0")}</div>
            {groups.length > 1 && (
              <button
                onClick={() => removeGroup(g.id)}
                className="mono text-[10px] text-[#808080] hover:text-[#FF0000]"
                data-testid={`repro-remove-group-${g.id}`}
              >REMOVE ✕</button>
            )}
          </div>

          <label className="block ae-border cursor-pointer p-4 hover:bg-[#0D0D0D]">
            <input
              type="file" multiple hidden
              onChange={(e) => onFiles(g.id, e.target.files)}
              data-testid={`repro-file-input-${g.id}`}
            />
            <div className="mono text-[10px] text-[#00FF41] tracking-widest">DROP EVIDENCE FILES →</div>
            <div className="mono text-[10px] text-[#808080] mt-1">
              {g.hashes.length === 0 ? "no files added" : `${g.hashes.length} file${g.hashes.length === 1 ? "" : "s"} · click to replace`}
            </div>
          </label>

          {g.hashes.length > 0 && (
            <>
              <div className="mt-4 space-y-1">
                {g.hashes.map((h, i) => (
                  <div key={i} className="mono text-[10px] flex items-center gap-3 border-b-[0.5px] border-[#1A1A1A] py-1">
                    <span className="text-[#808080] w-8 text-right">{String(i + 1).padStart(3, "0")}</span>
                    <span className="text-[#E8E8E8] truncate flex-1">{h.name}</span>
                    <span className="text-[#808080] w-16 text-right">{h.size}B</span>
                    <span className="text-[#00FF41] tracking-wider w-64 truncate text-right">{h.sha256.substr(0, 12)}…{h.sha256.substr(-12)}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 ae-border-strong px-4 py-3">
                <div className="mono text-[10px] text-[#808080] tracking-widest">// GROUP COMPOSITE SHA-256</div>
                <div className="mono text-[11px] text-[#00FF41] mt-1 break-all">{g.composite || "—"}</div>
              </div>
            </>
          )}
        </div>
      ))}

      <div className="px-6 py-4 border-b-[0.5px] border-[#1A1A1A]">
        <button
          onClick={addGroup}
          className="mono text-[10px] tracking-widest px-4 py-2 ae-border-strong text-[#808080] hover:text-[#00FF41]"
          data-testid="repro-add-group"
        >+ ADD AUDIT GROUP</button>
        <span className="mono text-[10px] text-[#808080] ml-4">{totalFiles} file{totalFiles === 1 ? "" : "s"} · {groups.filter(g => g.composite).length} audit group{groups.filter(g => g.composite).length === 1 ? "" : "s"}</span>
      </div>

      <div className="px-6 py-6 space-y-3">
        <div className="grid grid-cols-2 gap-0 ae-border-strong">
          <div className="p-4 border-r-[0.5px] border-[#2A2A2A]">
            <div className="mono text-[10px] text-[#808080] tracking-widest">// CLAIMED MERKLE ROOT</div>
            <div className="mono text-[11px] text-[#E8E8E8] mt-2 break-all">{targetRoot || "(paste a root above and verify)"}</div>
          </div>
          <div className="p-4">
            <div className="mono text-[10px] text-[#808080] tracking-widest">// YOUR COMPUTED ROOT</div>
            <div className="mono text-[11px] mt-2 break-all" style={{ color: result === "MATCH" ? "#00FF41" : result === "MISMATCH" ? "#FF0000" : "#808080" }}>
              {busy ? "COMPUTING…" : (merkle || "(add evidence files)")}
            </div>
          </div>
        </div>

        {result === "MATCH" && (
          <div className="ae-border-strong px-6 py-5" data-testid="repro-match">
            <div className="mono text-2xl tracking-widest" style={{ color: "#00FF41" }}>[DETERMINISTIC MATCH]</div>
            <div className="mono text-xs text-[#E8E8E8] mt-3 leading-relaxed">
              Your browser independently reproduced the exact Merkle root claimed on the Registry using only the public hashing schema (SHA-256, pipe-join, insertion-order).
              This proves the attestation is a <span className="text-[#00FF41]">deterministic protocol</span> — not a trusted intermediary.
              Any regulator with the same evidence arrives at the same root without contacting AuditEngine.
            </div>
          </div>
        )}
        {result === "MISMATCH" && (
          <div className="ae-border-strong px-6 py-5" data-testid="repro-mismatch">
            <div className="mono text-2xl tracking-widest" style={{ color: "#FF0000" }}>[MISMATCH]</div>
            <div className="mono text-xs text-[#E8E8E8] mt-3 leading-relaxed">
              Your locally computed root does not match the claimed root. Either the evidence set is incomplete, the file order differs, or the workspace has multiple audit groups — add each audit's files into its own group above.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
