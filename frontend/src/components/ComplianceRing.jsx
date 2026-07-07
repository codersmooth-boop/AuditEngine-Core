import React, { useEffect, useState } from "react";

export default function ComplianceRing({ score = 0, size = 180, animate = true }) {
  const [display, setDisplay] = useState(animate ? 0 : score);
  useEffect(() => {
    if (!animate) { setDisplay(score); return; }
    const start = performance.now();
    const dur = 800;
    let raf;
    const tick = (t) => {
      const p = Math.min(1, (t - start) / dur);
      setDisplay(Math.round(score * p));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [score, animate]);

  const color = display >= 80 ? "#00FF41" : display >= 60 ? "#FFBF00" : "#FF0000";
  const stroke = 4;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - Math.max(0, Math.min(100, display)) / 100);

  return (
    <div className="relative" style={{ width: size, height: size }} data-testid="compliance-ring">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#1A1A1A" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          stroke={color} strokeWidth={stroke} fill="none"
          strokeDasharray={c} strokeDashoffset={off}
          style={{ transition: "stroke 400ms" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="mono text-5xl font-light" style={{ color }} data-testid="compliance-score">{display}</div>
        <div className="mono text-[10px] text-[#808080] tracking-widest mt-1">SCORE / 100</div>
      </div>
    </div>
  );
}
