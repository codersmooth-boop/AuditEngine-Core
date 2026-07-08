import React, { useEffect, useRef, useState } from "react";

const STEPS = [
  "File Extraction",
  "Payload Writing",
  "Logic Engine Running",
  "Risk Map Generation",
  "PDF Delivery",
];

const TAG_COLOR = {
  OK: "#00FF41",
  SCAN: "#FFBF00",
  MATCH: "#00FF41",
  BREACH: "#FF0000",
  GAP: "#FFBF00",
  PLAN: "#00FF41",
  DONE: "#00FF41",
  FAIL: "#FF0000",
};

export default function ProcessingPanel({ step = 0, startedAt, logs = [], streamMode = "sse" }) {
  const [elapsed, setElapsed] = useState("00:00");
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!startedAt) return;
    const t = setInterval(() => {
      const s = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
      setElapsed(`${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`);
    }, 500);
    return () => clearInterval(t);
  }, [startedAt]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs.length]);

  return (
    <div className="ae-slide-up ae-border-strong border-t bg-[#050505]" data-testid="processing-panel">
      <div className="flex items-center justify-between px-8 py-3 ae-border border-b">
        <div className="mono text-[10px] tracking-[0.3em] text-[#00FF41]">
          // LOGIC ENGINE ACTIVE {streamMode === "poll" && <span className="text-[#FFBF00]">· FALLBACK: POLLING</span>}
        </div>
        <div className="mono text-[10px] text-[#808080]">
          ELAPSED <span className="text-[#E8E8E8]" data-testid="processing-timer">{elapsed}</span>
        </div>
      </div>
      <div className="grid grid-cols-5">
        {STEPS.map((label, i) => {
          const activeNow = step === i + 1;
          const doneNow = step > i + 1 || (step === 5 && i < 5);
          return (
            <div key={label} data-testid={`step-${i + 1}`} className={`p-6 ${i < 4 ? "border-r-[0.5px] border-[#1A1A1A]" : ""}`}>
              <div className="flex items-center gap-3">
                <span className={`w-3 h-3 inline-block ${doneNow ? "bg-[#00FF41]" : activeNow ? "bg-white ae-pulse" : "bg-transparent ae-border-strong"}`} />
                <span className="mono text-[10px] text-[#808080] tracking-widest">STEP {i + 1}</span>
              </div>
              <div className="mono text-xs mt-3 text-[#E8E8E8] uppercase">{label}</div>
              <div className={`mono text-[10px] mt-2 ${doneNow ? "text-[#00FF41]" : activeNow ? "text-white" : "text-[#333]"}`}>
                {doneNow ? "COMPLETE" : activeNow ? "RUNNING..." : "PENDING"}
              </div>
            </div>
          );
        })}
      </div>

      {/* Glass Box: live streaming terminal */}
      <div className="ae-border-strong border-t">
        <div className="flex items-center justify-between px-8 py-2 ae-border border-b">
          <div className="mono text-[10px] tracking-[0.3em] text-[#808080]">// GLASS BOX · EXECUTION SCRIPT</div>
          <div className="mono text-[10px] text-[#808080]">{logs.length} lines</div>
        </div>
        <div
          ref={scrollRef}
          data-testid="glass-box-terminal"
          className="bg-black h-64 overflow-y-auto px-8 py-4 font-[Roboto_Mono,monospace] text-[11px] leading-relaxed"
        >
          {logs.length === 0 && (
            <div className="text-[#808080] ae-cursor">STANDBY</div>
          )}
          {logs.map((l, i) => (
            <div key={i} className="whitespace-pre-wrap ae-fade-in">
              <span className="text-[#808080]">[{l.ts || "--:--:--"}] </span>
              <span className="text-[#E8E8E8]">{l.text}</span>
              <span className="ml-2" style={{ color: TAG_COLOR[l.tag] || "#00FF41" }}>[{l.tag || "OK"}]</span>
            </div>
          ))}
          {logs.length > 0 && step < 5 && (
            <div className="text-[#00FF41] ae-cursor mt-1">&gt;</div>
          )}
        </div>
      </div>
    </div>
  );
}
