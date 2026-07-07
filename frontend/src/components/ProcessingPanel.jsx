import React, { useEffect, useState } from "react";

const STEPS = [
  "File Extraction",
  "Payload Writing",
  "Logic Engine Running",
  "Risk Map Generation",
  "PDF Delivery",
];

export default function ProcessingPanel({ step = 0, startedAt }) {
  const [elapsed, setElapsed] = useState("00:00");
  useEffect(() => {
    if (!startedAt) return;
    const t = setInterval(() => {
      const s = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
      setElapsed(`${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`);
    }, 500);
    return () => clearInterval(t);
  }, [startedAt]);

  return (
    <div className="ae-slide-up ae-border-strong border-t bg-[#050505]" data-testid="processing-panel">
      <div className="flex items-center justify-between px-8 py-3 ae-border border-b">
        <div className="mono text-[10px] tracking-[0.3em] text-[#00FF41]">// LOGIC ENGINE ACTIVE</div>
        <div className="mono text-[10px] text-[#808080]">
          ELAPSED <span className="text-[#E8E8E8]" data-testid="processing-timer">{elapsed}</span>
        </div>
      </div>
      <div className="grid grid-cols-5">
        {STEPS.map((label, i) => {
          const state = step > i + 1 || step === 5 && i < 5 ? "done" : step === i + 1 ? "active" : "idle";
          const activeNow = step === i + 1;
          const doneNow = step > i + 1 || (step === 5 && i < 5);
          return (
            <div
              key={label}
              data-testid={`step-${i + 1}`}
              className={`p-6 ${i < 4 ? "border-r-[0.5px] border-[#1A1A1A]" : ""}`}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`w-3 h-3 inline-block ${
                    doneNow ? "bg-[#00FF41]"
                      : activeNow ? "bg-white ae-pulse"
                      : "bg-transparent ae-border-strong"
                  }`}
                />
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
    </div>
  );
}
