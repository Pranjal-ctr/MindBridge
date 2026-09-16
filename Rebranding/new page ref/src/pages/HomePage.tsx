import Mascot from "../components/Mascot";
import {
  HomeIcon, ChatIcon, GrowthIcon, JournalIcon, ActivitiesIcon, CounselorIcon,
  BellIcon, SettingsIcon, LogoutIcon, ClockIcon, SparkleIcon,
  MoodFace, ArrowRightIcon, ArrowLeftIcon,
} from "../components/Icons";
import { useState } from "react";

interface HomePageProps {
  onNavigate: (page: string) => void;
}

type MoodKey = "great" | "good" | "okay" | "notgreat" | "difficult";

const navItems = [
  { id: "home",       label: "Home",       Icon: HomeIcon,       sub: "" },
  { id: "comrade",    label: "Comrade",    Icon: ChatIcon,       sub: "Talk to Kio" },
  { id: "growth",     label: "Growth",     Icon: GrowthIcon,     sub: "Your progress" },
  { id: "journal",    label: "Journal",    Icon: JournalIcon,    sub: "Your space" },
  { id: "activities", label: "Activities", Icon: ActivitiesIcon, sub: "Small steps" },
  { id: "counselor",  label: "Counselor",  Icon: CounselorIcon,  sub: "Book a session" },
];

const moods: { key: MoodKey; label: string }[] = [
  { key: "great",    label: "Great" },
  { key: "good",     label: "Good" },
  { key: "okay",     label: "Okay" },
  { key: "notgreat", label: "Not great" },
  { key: "difficult",label: "Difficult" },
];

const actionCards = [
  {
    title: "Talk to Comrade",
    desc: "Share what's on your mind. Kio is here to listen.",
    Icon: ChatIcon,
    iconBg: "#EEF0FF",
    iconColor: "#6C5CE7",
    btn: "Start chat",
    btnBg: "#EEF0FF",
    btnColor: "#6C5CE7",
    bg: "#F5F4FF",
  },
  {
    title: "Write in Journal",
    desc: "A private space for your thoughts.",
    Icon: JournalIcon,
    iconBg: "#E6FFF8",
    iconColor: "#00997A",
    btn: "Open journal",
    btnBg: "#E6FFF8",
    btnColor: "#00997A",
    bg: "#F0FFF8",
    target: "journal",
  },
  {
    title: "Take a small step",
    desc: "Simple activities to feel a little better.",
    Icon: SparkleIcon,
    iconBg: "#FFF8E6",
    iconColor: "#D97706",
    btn: "Explore activities",
    btnBg: "#FFF8E6",
    btnColor: "#D97706",
    bg: "#FFFBF0",
  },
  {
    title: "Talk to a counselor",
    desc: "Book a session with a trusted counselor.",
    Icon: CounselorIcon,
    iconBg: "#FDE8F0",
    iconColor: "#C2185B",
    btn: "Book session",
    btnBg: "#FDE8F0",
    btnColor: "#C2185B",
    bg: "#FFF0F6",
  },
];

const recentChats = [
  { title: "Mood Shift From ...", date: "Today" },
  { title: "Maths exam stress", date: "Sep 12" },
  { title: "Loneliness and peace", date: "Sep 10" },
  { title: "Family pressure", date: "Sep 8" },
  { title: "New Conversation", date: "Sep 6" },
];

export default function HomePage({ onNavigate }: HomePageProps) {
  const [selectedMood, setSelectedMood] = useState<MoodKey | null>(null);

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#F5F4FF" }}>
      {/* Sidebar */}
      <aside className="flex flex-col" style={{ width: 224, minWidth: 224, background: "#fff", borderRight: "1px solid #E8E6F5", padding: "24px 0" }}>
        {/* Logo */}
        <div className="px-6 mb-6">
          <span style={{ fontFamily: "Nunito", fontWeight: 900, fontSize: 28, color: "#6C5CE7", letterSpacing: "-1px" }}>Kio</span>
        </div>

        {/* User */}
        <div className="flex items-center gap-3 px-5 mb-6">
          <div style={{ width: 42, height: 42, borderRadius: "50%", background: "linear-gradient(135deg,#a29bfe,#fd79a8)", flexShrink: 0 }}>
            <AvatarSVG />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: "#1A1A3E" }}>Priya</div>
            <div style={{ fontSize: 12, color: "#8B8BA7" }}>Class 11</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 px-3 flex-1">
          {navItems.map(({ id, label, Icon, sub }) => {
            const active = id === "home";
            return (
              <button
                key={id}
                onClick={() => onNavigate(id)}
                className="flex items-center gap-3 w-full text-left"
                style={{ padding: "10px 12px", borderRadius: 12, background: active ? "#EEF0FF" : "transparent", border: "none", cursor: "pointer", transition: "background 0.15s" }}
                onMouseEnter={(e) => { if (!active) (e.currentTarget as HTMLElement).style.background = "#F5F4FF"; }}
                onMouseLeave={(e) => { if (!active) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                <Icon color={active ? "#6C5CE7" : "#8B8BA7"} size={18} />
                <div>
                  <div style={{ fontSize: 14, fontWeight: active ? 700 : 600, color: active ? "#6C5CE7" : "#1A1A3E" }}>{label}</div>
                  {sub && <div style={{ fontSize: 11, color: "#8B8BA7" }}>{sub}</div>}
                </div>
              </button>
            );
          })}
        </nav>

        {/* Recent Chats */}
        <div className="px-5 mt-4">
          <div style={{ fontSize: 12, fontWeight: 700, color: "#8B8BA7", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            <ClockIcon size={13} color="#8B8BA7" /> Recent Chats
          </div>
          {recentChats.map((c, i) => (
            <div key={i} className="flex justify-between" style={{ marginBottom: 6 }}>
              <span style={{ fontSize: 12, color: "#1A1A3E", fontWeight: 500 }}>{c.title}</span>
              <span style={{ fontSize: 11, color: "#8B8BA7" }}>{c.date}</span>
            </div>
          ))}
          <button style={{ fontSize: 12, color: "#6C5CE7", fontWeight: 700, background: "none", border: "none", cursor: "pointer", padding: 0, marginTop: 4, fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 4 }}>
            View all chats <ArrowRightIcon size={13} color="#6C5CE7" />
          </button>
        </div>

        {/* Bottom */}
        <div className="px-5 mt-5 flex flex-col gap-2">
          <button style={{ fontSize: 13, color: "#8B8BA7", background: "none", border: "none", cursor: "pointer", textAlign: "left", padding: "4px 0", display: "flex", alignItems: "center", gap: 8, fontFamily: "Nunito" }}>
            <SettingsIcon size={15} color="#8B8BA7" /> Settings
          </button>
          <button style={{ fontSize: 13, color: "#8B8BA7", background: "none", border: "none", cursor: "pointer", textAlign: "left", padding: "4px 0", display: "flex", alignItems: "center", gap: 8, fontFamily: "Nunito" }}>
            <LogoutIcon size={15} color="#8B8BA7" /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        {/* Top bar */}
        <div className="flex items-center justify-end gap-4 sticky top-0 z-10" style={{ background: "rgba(245,244,255,0.9)", backdropFilter: "blur(8px)", padding: "14px 32px", borderBottom: "1px solid #E8E6F5" }}>
          <BellIcon size={20} color="#8B8BA7" />
          <span style={{ fontSize: 13, color: "#8B8BA7", fontWeight: 600 }}>Always here to listen · Safe &amp; Private</span>
          <div style={{ width: 34, height: 34, borderRadius: "50%", background: "linear-gradient(135deg,#a29bfe,#fd79a8)", overflow: "hidden", flexShrink: 0 }}>
            <AvatarSVG />
          </div>
        </div>

        <div style={{ padding: "32px 40px 56px" }} className="page-enter">
          {/* Hero */}
          <div className="flex items-start justify-between">
            <div>
              <h1 style={{ fontSize: 32, fontWeight: 900, color: "#1A1A3E", margin: 0, marginBottom: 6 }}>
                Good morning, Priya
                <span style={{ marginLeft: 10 }}><SunBadge /></span>
              </h1>
              <p style={{ fontSize: 16, fontWeight: 700, color: "#1A1A3E", margin: 0 }}>How are you feeling today?</p>
              <p style={{ fontSize: 14, color: "#8B8BA7", margin: "4px 0 0" }}>Your feelings matter. Take a moment to check in with yourself.</p>
            </div>
            <div className="flex flex-col items-end">
              <p style={{ fontFamily: "Caveat, cursive", fontSize: 20, color: "#6C5CE7", margin: "0 0 -10px", textAlign: "right", lineHeight: 1.35 }}>
                You're doing better<br />than you think ♡
              </p>
              <Mascot size={130} />
            </div>
          </div>

          {/* Mood check-in */}
          <div style={{ background: "#fff", borderRadius: 20, padding: "20px 24px", marginTop: 24, border: "1px solid #E8E6F5", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", gap: 24 }}>
              {moods.map((m) => (
                <button
                  key={m.key}
                  onClick={() => setSelectedMood(m.key)}
                  style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, background: "none", border: "none", cursor: "pointer", transition: "transform 0.15s", transform: selectedMood === m.key ? "scale(1.08)" : "scale(1)" }}
                >
                  <MoodFace mood={m.key} size={52} selected={selectedMood === m.key} />
                  <span style={{ fontSize: 12, fontWeight: 600, color: "#1A1A3E" }}>{m.label}</span>
                </button>
              ))}
            </div>
            <button style={{ fontSize: 14, color: "#6C5CE7", fontWeight: 700, background: "none", border: "none", cursor: "pointer", fontFamily: "Nunito" }}>
              Skip for now
            </button>
          </div>

          {/* What to do */}
          <div className="flex items-center justify-between" style={{ marginTop: 32, marginBottom: 16 }}>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: "#1A1A3E", margin: 0 }}>What would you like to do today?</h2>
            <span style={{ fontSize: 13, color: "#8B8BA7", fontStyle: "italic" }}>Small steps. A brighter you.</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
            {actionCards.map((card, i) => (
              <button
                key={i}
                onClick={() => card.target && onNavigate(card.target)}
                style={{ background: card.bg, borderRadius: 20, padding: "20px", border: "1px solid #E8E6F5", textAlign: "left", cursor: "pointer", fontFamily: "Nunito", display: "flex", flexDirection: "column", gap: 10, transition: "transform 0.15s, box-shadow 0.15s", position: "relative", overflow: "hidden" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.transform = "translateY(-3px)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 10px 28px rgba(108,92,231,0.13)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = "translateY(0)"; (e.currentTarget as HTMLElement).style.boxShadow = "none"; }}
              >
                {i === 0 ? (
                  /* Comrade card — mascot as the icon */
                  <div style={{ width: 56, height: 56, flexShrink: 0 }}>
                    <Mascot size={56} />
                  </div>
                ) : (
                  <div style={{ width: 44, height: 44, borderRadius: 13, background: card.iconBg, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <card.Icon color={card.iconColor} size={22} />
                  </div>
                )}
                <div style={{ fontSize: 15, fontWeight: 800, color: "#1A1A3E" }}>{card.title}</div>
                <div style={{ fontSize: 13, color: "#8B8BA7", lineHeight: 1.45 }}>{card.desc}</div>
                <div style={{ marginTop: 4, background: card.btnBg, color: card.btnColor, borderRadius: 10, padding: "8px 14px", fontSize: 13, fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}>
                  {card.btn} <ArrowRightIcon size={13} color={card.btnColor} />
                </div>
              </button>
            ))}
          </div>

          {/* Continue */}
          <div className="flex items-center justify-between" style={{ marginTop: 36, marginBottom: 14 }}>
            <h2 style={{ fontSize: 20, fontWeight: 800, color: "#1A1A3E", margin: 0 }}>Continue where you left off</h2>
            <button style={{ fontSize: 13, color: "#6C5CE7", fontWeight: 700, background: "none", border: "none", cursor: "pointer", fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 4 }}>
              View all chats <ArrowRightIcon size={13} color="#6C5CE7" />
            </button>
          </div>

          <div style={{ background: "#fff", borderRadius: 20, padding: "18px 24px", border: "1px solid #E8E6F5", display: "flex", alignItems: "center", gap: 16 }}>
            <div style={{ width: 44, height: 44, borderRadius: "50%", background: "#EEF0FF", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <ChatIcon size={22} color="#6C5CE7" />
            </div>
            <div className="flex-1">
              <div style={{ fontWeight: 700, fontSize: 15, color: "#1A1A3E" }}>Mood Shift From Lonely to Happy</div>
              <div style={{ fontSize: 13, color: "#8B8BA7", marginTop: 2 }}>I have a maths test on Friday and I keep putting off studying for it.</div>
            </div>
            <div style={{ fontSize: 12, color: "#8B8BA7", flexShrink: 0 }}>Last message · 10:08 PM</div>
            <button style={{ background: "#EEF0FF", color: "#6C5CE7", border: "none", borderRadius: 12, padding: "10px 18px", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "Nunito", flexShrink: 0, display: "flex", alignItems: "center", gap: 6 }}>
              Continue chat <ArrowRightIcon size={13} color="#6C5CE7" />
            </button>
          </div>

          {/* Footer quote */}
          <div style={{ marginTop: 44, textAlign: "center" }}>
            <p style={{ fontFamily: "Caveat, cursive", fontSize: 20, color: "#A29BFE", margin: 0 }}>"Progress, not perfection." — Kio</p>
          </div>
        </div>
      </main>
    </div>
  );
}

/* Inline SVG avatar so no emoji */
function AvatarSVG() {
  return (
    <svg width="42" height="42" viewBox="0 0 42 42" fill="none">
      <circle cx="21" cy="21" r="21" fill="url(#avatarGrad)" />
      <defs>
        <linearGradient id="avatarGrad" x1="0" y1="0" x2="42" y2="42">
          <stop stopColor="#a29bfe" /><stop offset="1" stopColor="#fd79a8" />
        </linearGradient>
      </defs>
      {/* Simple face */}
      <circle cx="21" cy="17" r="7" fill="#fff" opacity="0.9" />
      <ellipse cx="21" cy="34" rx="11" ry="8" fill="#fff" opacity="0.9" />
    </svg>
  );
}

function SunBadge() {
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none" style={{ display: "inline-block", verticalAlign: "middle" }}>
      <circle cx="15" cy="15" r="7" fill="#FCC419" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => {
        const rad = (deg * Math.PI) / 180;
        const x1 = 15 + 9 * Math.cos(rad), y1 = 15 + 9 * Math.sin(rad);
        const x2 = 15 + 12 * Math.cos(rad), y2 = 15 + 12 * Math.sin(rad);
        return <line key={deg} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#FCC419" strokeWidth="2" strokeLinecap="round" />;
      })}
    </svg>
  );
}
