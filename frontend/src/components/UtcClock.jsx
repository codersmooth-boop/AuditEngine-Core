import React, { useEffect, useState } from "react";

export default function UtcClock({ compact = false }) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  const hh = String(now.getUTCHours()).padStart(2, "0");
  const mm = String(now.getUTCMinutes()).padStart(2, "0");
  const ss = String(now.getUTCSeconds()).padStart(2, "0");
  return (
    <div className="mono text-[10px] text-[#808080] tracking-widest" data-testid="utc-clock">
      {compact ? `${hh}:${mm}:${ss}` : `UTC ${hh}:${mm}:${ss}`}
    </div>
  );
}
