interface IconProps {
  size?: number;
  color?: string;
  strokeWidth?: number;
}

const d = (color = "currentColor", sw = 1.8) => ({
  stroke: color,
  strokeWidth: sw,
  fill: "none",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export function HomeIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

export function ChatIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

export function GrowthIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  );
}

export function JournalIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
      <line x1="8" y1="7" x2="16" y2="7" />
      <line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  );
}

export function ActivitiesIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}

export function CounselorIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

export function BellIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 01-3.46 0" />
    </svg>
  );
}

export function SearchIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

export function SettingsIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
    </svg>
  );
}

export function LogoutIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

export function PenIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z" />
    </svg>
  );
}

export function CalendarIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

export function LeafIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M17 8C8 10 5.9 16.17 3.82 19.82A1 1 0 004.64 21c3.46-1.73 6.36-4.91 8.36-8.82" />
      <path d="M21 3C21 3 12 3 9 9c-1.08 2.16-.88 4.91 0 7" />
    </svg>
  );
}

export function FlameIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M8.5 14.5A2.5 2.5 0 0011 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 01-7 7 7 7 0 01-7-7c0-1.507.333-2.078.5-2.5" />
    </svg>
  );
}

export function BarChartIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  );
}

export function ShieldIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

export function LockIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0110 0v4" />
    </svg>
  );
}

export function TagIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z" />
      <line x1="7" y1="7" x2="7.01" y2="7" strokeWidth="2.5" />
    </svg>
  );
}

export function SparkleIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 2l1.8 5.4a1 1 0 00.63.63L20 10l-5.57 1.97a1 1 0 00-.63.63L12 18l-1.8-5.4a1 1 0 00-.63-.63L4 10l5.57-1.97a1 1 0 00.63-.63L12 2z" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 3l.5 1.5L7 5l-1.5.5L5 7l-.5-1.5L3 5l1.5-.5L5 3z" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M19 14l.5 1.5 1.5.5-1.5.5-.5 1.5-.5-1.5-1.5-.5 1.5-.5.5-1.5z" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SunIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

export function HeartIcon({ size = 20, color = "currentColor", fill = "none" }: IconProps & { fill?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" stroke={color} strokeWidth="1.8" fill={fill} strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" />
    </svg>
  );
}

export function TargetIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
}

export function GradCapIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
      <path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5" />
    </svg>
  );
}

export function UsersIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 00-3-3.87" />
      <path d="M16 3.13a4 4 0 010 7.75" />
    </svg>
  );
}

export function StarIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

export function LightbulbIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <line x1="9" y1="18" x2="15" y2="18" />
      <line x1="10" y1="22" x2="14" y2="22" />
      <path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0018 8 6 6 0 006 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 018.91 14" />
    </svg>
  );
}

export function ClockIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

export function ChevronRightIcon({ size = 16, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export function ArrowRightIcon({ size = 16, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

export function ArrowLeftIcon({ size = 16, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </svg>
  );
}

export function MoreVertIcon({ size = 18, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <circle cx="12" cy="5" r="1.5" />
      <circle cx="12" cy="12" r="1.5" />
      <circle cx="12" cy="19" r="1.5" />
    </svg>
  );
}

export function CheckCircleIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

export function InfoIcon({ size = 20, color = "currentColor" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...d(color)}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" strokeWidth="2.5" />
    </svg>
  );
}

/* Mood faces — stylised SVG circles, no emojis */
export function MoodFace({
  mood,
  size = 52,
  selected = false,
}: {
  mood: "great" | "good" | "okay" | "notgreat" | "difficult";
  size?: number;
  selected?: boolean;
}) {
  const configs = {
    great:    { bg: "#D3F9D8", ring: "#40C057", eyeY: 0.36, smileD: "M0.28 0.1 Q0.5 0.34 0.72 0.1", eyeSize: 0.07, eyeStyle: "filled" as const },
    good:     { bg: "#D3F9D8", ring: "#82C91E", eyeY: 0.38, smileD: "M0.3 0.12 Q0.5 0.3 0.7 0.12",  eyeSize: 0.065, eyeStyle: "filled" as const },
    okay:     { bg: "#FFF3BF", ring: "#F59F00", eyeY: 0.38, smileD: "M0.32 0.16 L0.68 0.16",        eyeSize: 0.065, eyeStyle: "filled" as const },
    notgreat: { bg: "#FFE8CC", ring: "#F76707", eyeY: 0.36, smileD: "M0.3 0.18 Q0.5 0.05 0.7 0.18", eyeSize: 0.065, eyeStyle: "filled" as const },
    difficult:{ bg: "#FFD6E7", ring: "#E64980", eyeY: 0.36, smileD: "M0.28 0.18 Q0.5 0.04 0.72 0.18",eyeSize: 0.07, eyeStyle: "tears" as const },
  };
  const c = configs[mood];
  const s = size;
  const cx = s / 2, cy = s / 2, r = s * 0.42;
  const eyeLx = cx - r * 0.3, eyeRx = cx + r * 0.3;
  const eyeY = cy - r * 0.15;
  const eyeR = r * c.eyeSize * (s / 52);
  const smileScale = r * 0.75;
  const smileYBase = cy + r * 0.1;

  // Parse smile path segments scaled to circle
  const parsedSmile = c.smileD
    .replace(/[\d.]+/g, (n, i, str) => {
      const before = str.slice(0, i);
      const isY = (before.match(/[ML,Q]\s*[\d.]+\s*$/));
      return String(parseFloat(n) * smileScale);
    });

  return (
    <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} style={{ overflow: "visible" }}>
      <circle cx={cx} cy={cy} r={r} fill={c.bg} stroke={selected ? c.ring : "transparent"} strokeWidth={selected ? 3 : 0} />
      {selected && <circle cx={cx} cy={cy} r={r + 5} fill="none" stroke={c.ring} strokeWidth="2" opacity="0.3" />}

      {/* Eyes */}
      <circle cx={eyeLx} cy={eyeY} r={eyeR} fill="#2D2D6E" />
      <circle cx={eyeRx} cy={eyeY} r={eyeR} fill="#2D2D6E" />

      {/* Smile */}
      {mood === "great" && (
        <path d={`M${cx - r * 0.38} ${smileYBase} Q${cx} ${smileYBase + r * 0.38} ${cx + r * 0.38} ${smileYBase}`} stroke="#2D2D6E" strokeWidth={s * 0.045} fill="none" strokeLinecap="round" />
      )}
      {mood === "good" && (
        <path d={`M${cx - r * 0.32} ${smileYBase} Q${cx} ${smileYBase + r * 0.28} ${cx + r * 0.32} ${smileYBase}`} stroke="#2D2D6E" strokeWidth={s * 0.04} fill="none" strokeLinecap="round" />
      )}
      {mood === "okay" && (
        <line x1={cx - r * 0.28} y1={smileYBase + r * 0.04} x2={cx + r * 0.28} y2={smileYBase + r * 0.04} stroke="#2D2D6E" strokeWidth={s * 0.04} strokeLinecap="round" />
      )}
      {mood === "notgreat" && (
        <path d={`M${cx - r * 0.32} ${smileYBase + r * 0.2} Q${cx} ${smileYBase - r * 0.08} ${cx + r * 0.32} ${smileYBase + r * 0.2}`} stroke="#2D2D6E" strokeWidth={s * 0.04} fill="none" strokeLinecap="round" />
      )}
      {mood === "difficult" && (
        <>
          <path d={`M${cx - r * 0.36} ${smileYBase + r * 0.24} Q${cx} ${smileYBase - r * 0.12} ${cx + r * 0.36} ${smileYBase + r * 0.24}`} stroke="#2D2D6E" strokeWidth={s * 0.045} fill="none" strokeLinecap="round" />
          {/* Tears */}
          <ellipse cx={eyeLx + r * 0.05} cy={eyeY + r * 0.3} rx={r * 0.08} ry={r * 0.13} fill="#74b9ff" opacity="0.7" />
          <ellipse cx={eyeRx - r * 0.05} cy={eyeY + r * 0.3} rx={r * 0.08} ry={r * 0.13} fill="#74b9ff" opacity="0.7" />
        </>
      )}
    </svg>
  );
}
