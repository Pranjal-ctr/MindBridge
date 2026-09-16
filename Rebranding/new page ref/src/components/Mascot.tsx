import { useEffect, useState } from "react";

interface MascotProps {
  size?: number;
  className?: string;
}

export default function Mascot({ size = 140, className = "" }: MascotProps) {
  const [eyesClosed, setEyesClosed] = useState(false);

  useEffect(() => {
    // Double-blink: close → open → close → open
    const doubleBlink = () => {
      setEyesClosed(true);
      setTimeout(() => {
        setEyesClosed(false);
        setTimeout(() => {
          setEyesClosed(true);
          setTimeout(() => setEyesClosed(false), 140);
        }, 120);
      }, 140);
    };

    const interval = setInterval(doubleBlink, 3800);
    const first = setTimeout(doubleBlink, 1200);
    return () => { clearInterval(interval); clearTimeout(first); };
  }, []);

  const cx = size / 2;
  const cy = size / 2;
  const r  = size * 0.34;

  // Eye positions
  const eyeLx = cx - r * 0.28;
  const eyeRx = cx + r * 0.28;
  const eyeY  = cy - r * 0.18;
  const eyeR  = r * 0.1;

  return (
    <div
      className={`relative inline-flex items-center justify-center mascot-float ${className}`}
      style={{ width: size, height: size }}
    >
      {/* Soft ambient glow — purple left, cyan right */}
      <div
        className="absolute mascot-glow"
        style={{
          inset: "2%",
          borderRadius: "50%",
          background:
            "radial-gradient(ellipse at 28% 42%, #c4b5fd 0%, #818cf8 40%, #67e8f9 75%, #a5f3fc 100%)",
          filter: "blur(10px)",
          opacity: 0.28,
        }}
      />

      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="relative z-10 mascot-breathe"
        style={{ overflow: "visible" }}
      >
        <defs>
          {/* ── 3-D sphere base: bright upper-left → lavender lower-right ── */}
          <radialGradient id={`bodyGrad-${size}`} cx="33%" cy="28%" r="72%">
            <stop offset="0%"   stopColor="#ffffff" />
            <stop offset="45%"  stopColor="#f5f3ff" />
            <stop offset="78%"  stopColor="#ede9fe" />
            <stop offset="100%" stopColor="#ddd6fe" />
          </radialGradient>

          {/* ── Specular highlight blob ── */}
          <radialGradient id={`spec-${size}`} cx="36%" cy="26%" r="38%">
            <stop offset="0%"   stopColor="#ffffff" stopOpacity="0.96" />
            <stop offset="55%"  stopColor="#ffffff" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </radialGradient>

          {/* ── Bottom rim shadow (gives roundness) ── */}
          <radialGradient id={`rim-${size}`} cx="54%" cy="88%" r="52%">
            <stop offset="0%"   stopColor="#6c5ce7" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#6c5ce7" stopOpacity="0" />
          </radialGradient>

          {/* ── Eye shine ── */}
          <radialGradient id={`eyeShine-${size}`} cx="30%" cy="28%" r="55%">
            <stop offset="0%"   stopColor="#ffffff" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </radialGradient>

          {/* Soft drop shadow filter */}
          <filter id={`shadow-${size}`} x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy={size * 0.04} stdDeviation={size * 0.06}
              floodColor="#7c6ee6" floodOpacity="0.22" />
          </filter>
        </defs>

        {/* ── Sphere body ── */}
        <circle
          cx={cx} cy={cy} r={r}
          fill={`url(#bodyGrad-${size})`}
          filter={`url(#shadow-${size})`}
        />

        {/* ── Rim shadow overlay (bottom roundness) ── */}
        <circle
          cx={cx} cy={cy} r={r}
          fill={`url(#rim-${size})`}
        />

        {/* ── Specular highlight (upper-left shine) ── */}
        <ellipse
          cx={cx - r * 0.22}
          cy={cy - r * 0.28}
          rx={r * 0.48}
          ry={r * 0.34}
          fill={`url(#spec-${size})`}
          style={{ mixBlendMode: "screen" }}
        />

        {/* ── Eyes ── */}
        {eyesClosed ? (
          <>
            {/* Closed — flat line (both lids meeting) */}
            <line
              x1={eyeLx - eyeR * 1.1} y1={eyeY}
              x2={eyeLx + eyeR * 1.1} y2={eyeY}
              stroke="#3730a3" strokeWidth={size * 0.026} strokeLinecap="round"
            />
            <line
              x1={eyeRx - eyeR * 1.1} y1={eyeY}
              x2={eyeRx + eyeR * 1.1} y2={eyeY}
              stroke="#3730a3" strokeWidth={size * 0.026} strokeLinecap="round"
            />
          </>
        ) : (
          <>
            {/* Left eye */}
            <circle cx={eyeLx} cy={eyeY} r={eyeR} fill="#3730a3" />
            {/* Left eye shine */}
            <ellipse
              cx={eyeLx + eyeR * 0.32}
              cy={eyeY - eyeR * 0.38}
              rx={eyeR * 0.38}
              ry={eyeR * 0.3}
              fill="#ffffff"
              opacity="0.88"
            />

            {/* Right eye */}
            <circle cx={eyeRx} cy={eyeY} r={eyeR} fill="#3730a3" />
            {/* Right eye shine */}
            <ellipse
              cx={eyeRx + eyeR * 0.32}
              cy={eyeY - eyeR * 0.38}
              rx={eyeR * 0.38}
              ry={eyeR * 0.3}
              fill="#ffffff"
              opacity="0.88"
            />
          </>
        )}

        {/* ── Smile ── */}
        <path
          d={`M${cx - r * 0.22} ${cy + r * 0.28} Q${cx} ${cy + r * 0.44} ${cx + r * 0.22} ${cy + r * 0.28}`}
          stroke="#3730a3"
          strokeWidth={size * 0.028}
          strokeLinecap="round"
          fill="none"
          opacity="0.85"
        />
      </svg>
    </div>
  );
}
