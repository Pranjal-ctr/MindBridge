import { useState } from "react";
import Mascot from "../components/Mascot";
import {
  GrowthIcon, BellIcon, SearchIcon, TargetIcon, GradCapIcon, HeartIcon,
  UsersIcon, SparkleIcon, StarIcon, LightbulbIcon, ShieldIcon, BarChartIcon,
  JournalIcon, ChatIcon, ArrowRightIcon, ArrowLeftIcon, ChevronRightIcon,
  CheckCircleIcon,
} from "../components/Icons";

interface GrowthPageProps {
  onNavigate: (page: string) => void;
}

const navLinks = ["home", "comrade", "wellness", "growth", "journal", "resources"];
const navLabels: Record<string, string> = {
  home: "Home", comrade: "Chat", wellness: "Wellness",
  growth: "Growth", journal: "Journal", resources: "Resources",
};

const totalMemories = 27;
const areas = [
  { Icon: TargetIcon,  title: "Goals & Aspirations", sub: "Your dreams and future", memories: 6,  bg: "#FFF3E0", iconBg: "#FEF3C7", iconColor: "#D97706", barColor: "#F59F00" },
  { Icon: GradCapIcon, title: "Academic",             sub: "Studies & learning",    memories: 5,  bg: "#EFF6FF", iconBg: "#DBEAFE", iconColor: "#2563EB", barColor: "#4DABF7" },
  { Icon: HeartIcon,   title: "Emotional Wellbeing",  sub: "Feelings & challenges", memories: 11, bg: "#FDF2F8", iconBg: "#FCE7F3", iconColor: "#BE185D", barColor: "#E64980" },
  { Icon: UsersIcon,   title: "Relationships",        sub: "Family & friends",      memories: 4,  bg: "#F5F3FF", iconBg: "#EDE9FE", iconColor: "#6D28D9", barColor: "#7950F2" },
  { Icon: SparkleIcon, title: "About You",            sub: "Things that make you",  memories: 1,  bg: "#F9FAFB", iconBg: "#F3F4F6", iconColor: "#6B7280", barColor: "#9CA3AF" },
];

const currentPicture = [
  { Icon: TargetIcon,  color: "#D97706", bg: "#FEF3C7", text: "Exploring your future and career options",             strength: 82 },
  { Icon: GradCapIcon, color: "#2563EB", bg: "#DBEAFE", text: "Working hard in your studies, especially mathematics",  strength: 74 },
  { Icon: HeartIcon,   color: "#BE185D", bg: "#FCE7F3", text: "Experiencing some stress and pressure at times",        strength: 91 },
  { Icon: UsersIcon,   color: "#6D28D9", bg: "#EDE9FE", text: "You value your family and close relationships",         strength: 68 },
  { Icon: SparkleIcon, color: "#059669", bg: "#D1FAE5", text: "You're trying to find more peace and confidence",       strength: 60 },
];

const reflections = [
  { Icon: JournalIcon, iconColor: "#2563EB", text: "Preparing for your maths exam",                                   date: "Sep 15", area: "Academic" },
  { Icon: UsersIcon,   iconColor: "#6D28D9", text: "Feeling family pressure",                                          date: "Sep 8",  area: "Relationships" },
  { Icon: HeartIcon,   iconColor: "#BE185D", text: "Looking for ways to feel calmer",                                  date: "Sep 7",  area: "Emotional" },
  { Icon: TargetIcon,  iconColor: "#D97706", text: "Exploring engineering and medicine as future paths",               date: "Sep 3",  area: "Goals" },
  { Icon: SparkleIcon, iconColor: "#059669", text: "Wanting to spend more quality time with people you care about",   date: "Aug 28", area: "About You" },
];

// Simulated weekly activity — true = had a check-in that day
const weeks = [
  [true,  true,  false, true,  true,  false, false],
  [false, true,  true,  true,  false, true,  false],
  [true,  false, true,  true,  true,  false, true ],
  [true,  true,  true,  false, true,  true,  false],
];
const dayLabels = ["M", "T", "W", "T", "F", "S", "S"];

const areaTagColors: Record<string, { bg: string; color: string }> = {
  Academic:      { bg: "#DBEAFE", color: "#1D4ED8" },
  Relationships: { bg: "#EDE9FE", color: "#5B21B6" },
  Emotional:     { bg: "#FCE7F3", color: "#9D174D" },
  Goals:         { bg: "#FEF3C7", color: "#92400E" },
  "About You":   { bg: "#D1FAE5", color: "#065F46" },
};

export default function GrowthPage({ onNavigate }: GrowthPageProps) {
  const [activeArea, setActiveArea] = useState<number | null>(null);

  return (
    <div style={{ minHeight: "100vh", background: "#F5F4FF", fontFamily: "Nunito, sans-serif" }}>
      {/* Top Nav */}
      <nav style={{ background: "#fff", borderBottom: "1px solid #E8E6F5", padding: "0 32px", display: "flex", alignItems: "center", height: 60, gap: 28, position: "sticky", top: 0, zIndex: 20 }}>
        <span style={{ fontWeight: 900, fontSize: 26, color: "#6C5CE7", marginRight: 8 }}>Kio</span>
        {navLinks.map((id) => (
          <button key={id} onClick={() => onNavigate(id)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14, fontWeight: id === "growth" ? 700 : 600, color: id === "growth" ? "#6C5CE7" : "#8B8BA7", borderBottom: id === "growth" ? "2px solid #6C5CE7" : "2px solid transparent", padding: "18px 2px", fontFamily: "Nunito, sans-serif", transition: "color 0.15s" }}>
            {navLabels[id]}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <SearchIcon size={19} color="#8B8BA7" />
        <BellIcon size={19} color="#8B8BA7" />
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <AvatarCircle />
          <div style={{ lineHeight: 1.1 }}>
            <div style={{ fontSize: 13, fontWeight: 700 }}>Priya</div>
            <div style={{ fontSize: 11, color: "#8B8BA7" }}>Class 11</div>
          </div>
        </div>
      </nav>

      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "0 28px 72px" }} className="page-enter">
        {/* Back */}
        <button onClick={() => onNavigate("home")} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14, color: "#6C5CE7", fontWeight: 600, padding: "18px 0", fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 6 }}>
          <ArrowLeftIcon size={14} color="#6C5CE7" /> Back to Dashboard
        </button>

        {/* Hero */}
        <div style={{ background: "linear-gradient(135deg,#EEF0FF 0%,#E8F4FD 50%,#F0FFF8 100%)", borderRadius: 28, padding: "32px 36px", display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, overflow: "hidden", position: "relative" }}>
          {/* Decorative circle */}
          <div style={{ position: "absolute", right: 200, top: -40, width: 220, height: 220, borderRadius: "50%", background: "radial-gradient(circle,#c4b5fd22 0%,#67e8f900 70%)", pointerEvents: "none" }} />
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
              <div style={{ width: 52, height: 52, background: "#EEF0FF", borderRadius: 16, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <GrowthIcon size={28} color="#6C5CE7" />
              </div>
              <div>
                <h1 style={{ fontSize: 30, fontWeight: 900, color: "#1A1A3E", margin: 0, letterSpacing: "-0.5px" }}>My Growth Profile</h1>
                <p style={{ fontSize: 14, color: "#8B8BA7", margin: 0 }}>A reflection of what you've shared with Kio over time.</p>
              </div>
            </div>
            {/* Stats row */}
            <div style={{ display: "flex", gap: 10 }}>
              {[
                { val: "27", label: "memories",        accent: "#6C5CE7" },
                { val: "5",  label: "life areas",      accent: "#00997A" },
                { val: "3",  label: "months together", accent: "#D97706" },
              ].map((s, i) => (
                <div key={i} style={{ background: "#fff", borderRadius: 16, padding: "12px 20px", display: "flex", alignItems: "center", gap: 10, boxShadow: "0 2px 8px rgba(108,92,231,0.07)" }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: s.accent }} />
                  <div>
                    <div style={{ fontWeight: 900, fontSize: 20, color: "#1A1A3E", lineHeight: 1 }}>{s.val}</div>
                    <div style={{ fontSize: 11, color: "#8B8BA7", marginTop: 2 }}>{s.label}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
            <p style={{ fontFamily: "Caveat, cursive", fontSize: 19, color: "#6C5CE7", textAlign: "right", margin: 0, lineHeight: 1.4 }}>
              A kinder<br />brighter you<br />is a work in progress ♡
            </p>
            <Mascot size={124} />
          </div>
        </div>

        {/* Showing up banner */}
        <div style={{ background: "#fff", borderRadius: 20, padding: "18px 24px", border: "1px solid #E8E6F5", display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28, boxShadow: "0 2px 12px rgba(108,92,231,0.05)" }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            <div style={{ width: 44, height: 44, borderRadius: 13, background: "linear-gradient(135deg,#FEF3C7,#FDE68A)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <StarIcon size={22} color="#D97706" />
            </div>
            <div>
              <p style={{ fontWeight: 800, fontSize: 15, color: "#1A1A3E", margin: "0 0 3px" }}>You're showing up, and that matters</p>
              <p style={{ fontSize: 13, color: "#8B8BA7", margin: 0, lineHeight: 1.5 }}>You've been open about your thoughts, feelings and goals. Kio remembers what matters to you.</p>
            </div>
          </div>
          <button style={{ background: "#EEF0FF", color: "#6C5CE7", border: "none", borderRadius: 14, padding: "10px 18px", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 6, flexShrink: 0, transition: "background 0.15s" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#ddd6fe")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#EEF0FF")}
          >
            Manage memories <ChevronRightIcon size={14} color="#6C5CE7" />
          </button>
        </div>

        {/* Areas of your life */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <h2 style={{ fontSize: 19, fontWeight: 800, color: "#1A1A3E", margin: 0 }}>Areas of your life</h2>
          <span style={{ fontSize: 13, color: "#8B8BA7" }}>Explore what Kio understands about you</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 12, marginBottom: 28 }}>
          {areas.map((a, i) => {
            const pct = Math.round((a.memories / totalMemories) * 100);
            const isActive = activeArea === i;
            return (
              <button
                key={i}
                onClick={() => setActiveArea(isActive ? null : i)}
                style={{ background: isActive ? a.bg : "#fff", border: `1.5px solid ${isActive ? a.barColor + "60" : "#E8E6F5"}`, borderRadius: 20, padding: "18px 16px", textAlign: "left", cursor: "pointer", fontFamily: "Nunito", display: "flex", flexDirection: "column", gap: 10, transition: "all 0.18s", boxShadow: isActive ? `0 6px 20px ${a.barColor}22` : "0 2px 8px rgba(0,0,0,0.04)" }}
                onMouseEnter={(e) => { if (!isActive) { (e.currentTarget as HTMLElement).style.transform = "translateY(-3px)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 10px 24px rgba(108,92,231,0.1)"; } }}
                onMouseLeave={(e) => { if (!isActive) { (e.currentTarget as HTMLElement).style.transform = "translateY(0)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 2px 8px rgba(0,0,0,0.04)"; } }}
              >
                <div style={{ width: 44, height: 44, borderRadius: 13, background: a.iconBg, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <a.Icon size={22} color={a.iconColor} />
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 13, color: "#1A1A3E", marginBottom: 2 }}>{a.title}</div>
                  <div style={{ fontSize: 11, color: "#8B8BA7" }}>{a.sub}</div>
                </div>
                {/* Progress bar */}
                <div>
                  <div style={{ height: 5, background: "#F0EFF9", borderRadius: 10, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: a.barColor, borderRadius: 10, transition: "width 0.6s ease" }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5 }}>
                    <span style={{ fontSize: 11, color: "#8B8BA7" }}>{a.memories} memories</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: a.iconColor }}>{pct}%</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Activity streak */}
        <div style={{ background: "#fff", borderRadius: 20, padding: "20px 24px", border: "1px solid #E8E6F5", marginBottom: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <BarChartIcon size={18} color="#6C5CE7" />
              <span style={{ fontWeight: 700, fontSize: 15, color: "#1A1A3E" }}>Your check-in activity</span>
            </div>
            <div style={{ display: "flex", gap: 16 }}>
              {[
                { val: "18", label: "check-ins", color: "#6C5CE7" },
                { val: "3",  label: "week streak", color: "#00997A" },
                { val: "Sep", label: "best month", color: "#D97706" },
              ].map((s, i) => (
                <div key={i} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 16, fontWeight: 900, color: s.color }}>{s.val}</div>
                  <div style={{ fontSize: 11, color: "#8B8BA7" }}>{s.label}</div>
                </div>
              ))}
            </div>
          </div>
          {/* Heatmap grid */}
          <div style={{ display: "flex", gap: 4, alignItems: "flex-start" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, marginRight: 4, paddingTop: 2 }}>
              {["W1", "W2", "W3", "W4"].map((w) => (
                <div key={w} style={{ fontSize: 10, color: "#C8C4E0", height: 22, display: "flex", alignItems: "center" }}>{w}</div>
              ))}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 4, marginBottom: 4 }}>
                {dayLabels.map((d, i) => (
                  <div key={i} style={{ fontSize: 10, color: "#8B8BA7", textAlign: "center", fontWeight: 600 }}>{d}</div>
                ))}
              </div>
              {weeks.map((week, wi) => (
                <div key={wi} style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 4, marginBottom: 4 }}>
                  {week.map((active, di) => (
                    <div
                      key={di}
                      title={active ? "Check-in recorded" : "No check-in"}
                      style={{
                        height: 22,
                        borderRadius: 6,
                        background: active
                          ? `linear-gradient(135deg, #a29bfe, #818cf8)`
                          : "#F0EFF9",
                        transition: "transform 0.1s",
                        cursor: "default",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.15)")}
                      onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Current picture + Reflections */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
          {/* Current picture */}
          <div style={{ background: "#fff", borderRadius: 20, padding: "22px 24px", border: "1px solid #E8E6F5", boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <BarChartIcon size={18} color="#6C5CE7" />
              <span style={{ fontWeight: 700, fontSize: 15, color: "#1A1A3E" }}>Your current picture</span>
            </div>
            <p style={{ fontSize: 13, color: "#8B8BA7", margin: "0 0 18px" }}>Themes Kio sees from your recent conversations</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {currentPicture.map((item, i) => (
                <div key={i}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                    <div style={{ width: 28, height: 28, borderRadius: 8, background: item.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <item.Icon size={15} color={item.color} />
                    </div>
                    <span style={{ fontSize: 13, color: "#1A1A3E", lineHeight: 1.4, flex: 1 }}>{item.text}</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: item.color, flexShrink: 0 }}>{item.strength}%</span>
                  </div>
                  <div style={{ height: 4, background: "#F0EFF9", borderRadius: 10, overflow: "hidden", marginLeft: 38 }}>
                    <div style={{ height: "100%", width: `${item.strength}%`, background: item.color, borderRadius: 10, opacity: 0.6 }} />
                  </div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 16, background: "#F5F4FF", borderRadius: 12, padding: "11px 14px", display: "flex", gap: 8, alignItems: "flex-start" }}>
              <ShieldIcon size={15} color="#6C5CE7" />
              <p style={{ fontSize: 12, color: "#8B8BA7", margin: 0, lineHeight: 1.5 }}>These insights are based on what you've chosen to share. Edit or remove any memory anytime.</p>
            </div>
          </div>

          {/* Recent reflections — timeline style */}
          <div style={{ background: "#fff", borderRadius: 20, padding: "22px 24px", border: "1px solid #E8E6F5", boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <ChatIcon size={18} color="#6C5CE7" />
                <span style={{ fontWeight: 700, fontSize: 15, color: "#1A1A3E" }}>Recent reflections</span>
              </div>
              <button style={{ fontSize: 13, color: "#6C5CE7", fontWeight: 700, background: "none", border: "none", cursor: "pointer", fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 4 }}>
                View all <ArrowRightIcon size={13} color="#6C5CE7" />
              </button>
            </div>
            <p style={{ fontSize: 13, color: "#8B8BA7", margin: "0 0 18px" }}>Some of the things we've talked about recently</p>

            {/* Timeline */}
            <div style={{ position: "relative", paddingLeft: 20 }}>
              {/* Vertical line */}
              <div style={{ position: "absolute", left: 7, top: 6, bottom: 6, width: 2, background: "linear-gradient(to bottom,#a29bfe,#c4b5fd44)", borderRadius: 2 }} />
              {reflections.map((r, i) => {
                const tagStyle = areaTagColors[r.area] || { bg: "#F0EFF9", color: "#6C5CE7" };
                return (
                  <div key={i} style={{ position: "relative", display: "flex", gap: 12, marginBottom: i < reflections.length - 1 ? 16 : 0, alignItems: "flex-start" }}>
                    {/* Dot on timeline */}
                    <div style={{ position: "absolute", left: -16, top: 6, width: 10, height: 10, borderRadius: "50%", background: r.iconColor, border: "2px solid #fff", boxShadow: `0 0 0 2px ${r.iconColor}44` }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
                        <span style={{ fontSize: 13, color: "#1A1A3E", lineHeight: 1.4, flex: 1 }}>{r.text}</span>
                        <span style={{ fontSize: 11, color: "#8B8BA7", flexShrink: 0, marginTop: 1 }}>{r.date}</span>
                      </div>
                      <span style={{ display: "inline-block", marginTop: 5, fontSize: 11, fontWeight: 700, background: tagStyle.bg, color: tagStyle.color, borderRadius: 20, padding: "2px 10px" }}>
                        {r.area}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* You're in control */}
        <div style={{ background: "linear-gradient(135deg,#EEF0FF,#E0F2FE)", borderRadius: 20, padding: "20px 28px", border: "1px solid #E8E6F5", display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <div style={{ width: 46, height: 46, borderRadius: 14, background: "#fff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "0 2px 8px rgba(108,92,231,0.12)" }}>
              <LightbulbIcon size={24} color="#6C5CE7" />
            </div>
            <div>
              <p style={{ fontWeight: 800, fontSize: 15, color: "#1A1A3E", margin: "0 0 3px" }}>You're in control</p>
              <p style={{ fontSize: 13, color: "#8B8BA7", margin: 0 }}>Review, edit, or remove what Kio remembers. We only keep what you're comfortable with.</p>
            </div>
          </div>
          <button style={{ background: "#fff", color: "#6C5CE7", border: "1px solid #E8E6F5", borderRadius: 14, padding: "10px 20px", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 6, flexShrink: 0, boxShadow: "0 2px 8px rgba(108,92,231,0.08)" }}>
            <ShieldIcon size={15} color="#6C5CE7" /> Manage my memories <ChevronRightIcon size={14} color="#6C5CE7" />
          </button>
        </div>

        {/* Footer */}
        <div style={{ background: "linear-gradient(135deg,#6C5CE7 0%,#818cf8 100%)", borderRadius: 24, padding: "28px 36px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <CheckCircleIcon size={28} color="rgba(255,255,255,0.9)" />
            <div>
              <p style={{ fontWeight: 800, fontSize: 16, color: "#fff", margin: "0 0 4px" }}>This is your story, and it's still being written.</p>
              <p style={{ fontSize: 13, color: "rgba(255,255,255,0.72)", margin: 0 }}>You're learning, growing and navigating life — and Kio is here to support you along the way.</p>
            </div>
          </div>
          <p style={{ fontFamily: "Caveat, cursive", fontSize: 20, color: "rgba(255,255,255,0.85)", textAlign: "right", margin: 0, lineHeight: 1.4, flexShrink: 0 }}>
            Small steps<br />still count ♡
          </p>
        </div>
      </div>
    </div>
  );
}

function AvatarCircle() {
  return (
    <div style={{ width: 34, height: 34, borderRadius: "50%", background: "linear-gradient(135deg,#a29bfe,#74b9ff)", overflow: "hidden", flexShrink: 0 }}>
      <svg width="34" height="34" viewBox="0 0 34 34" fill="none">
        <circle cx="17" cy="14" r="6" fill="#fff" opacity="0.9" />
        <ellipse cx="17" cy="28" rx="10" ry="7" fill="#fff" opacity="0.9" />
      </svg>
    </div>
  );
}
