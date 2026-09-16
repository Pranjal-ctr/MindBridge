import { useState } from "react";
import Mascot from "../components/Mascot";
import {
  JournalIcon, ChatIcon, GrowthIcon, BellIcon, SearchIcon,
  PenIcon, CalendarIcon, LeafIcon, FlameIcon, BarChartIcon,
  ShieldIcon, LockIcon, TagIcon, SparkleIcon, SunIcon, HeartIcon,
  TargetIcon, MoodFace, ArrowRightIcon, ArrowLeftIcon, MoreVertIcon,
} from "../components/Icons";
import { type MoodKey } from "./types";

interface JournalPageProps {
  onNavigate: (page: string) => void;
}

const tags = ["School", "Family", "Friends", "Wellbeing", "Future", "Other"];

const prompts = [
  { Icon: SunIcon,    iconColor: "#D97706", title: "My day",        sub: "What happened today?",              bg: "#FFF8E6" },
  { Icon: HeartIcon,  iconColor: "#C2185B", title: "On my mind",    sub: "What's been on your mind lately?",  bg: "#FDE8F0" },
  { Icon: LeafIcon,   iconColor: "#00997A", title: "Gratitude",     sub: "What are you grateful for today?",  bg: "#E6FFF8" },
  { Icon: TargetIcon, iconColor: "#6C5CE7", title: "Looking ahead", sub: "What do you want for the coming week?", bg: "#EEF0FF" },
];

const recentEntries = [
  { date: ["SEP","15"], title: "A better day",           preview: "Today felt lighter. I had a good conversation with my friend and felt more confident ...", mood: "good" as MoodKey,  tags: ["Friends", "Wellbeing"] },
  { date: ["SEP","12"], title: "Exam stress",            preview: "I've been feeling overwhelmed about the maths exam. I need to plan better ...",          mood: "notgreat" as MoodKey, tags: ["School"] },
  { date: ["SEP","10"], title: "Things I'm grateful for",preview: "I'm grateful for my family, my friends, and the opportunities I have ...",               mood: "great" as MoodKey, tags: ["Gratitude"] },
];

const navLinks = [
  { id: "home",      label: "Home",      Icon: null },
  { id: "comrade",   label: "Chat",      Icon: null },
  { id: "wellness",  label: "Wellness",  Icon: null },
  { id: "growth",    label: "Growth",    Icon: null },
  { id: "journal",   label: "Journal",   Icon: null },
  { id: "resources", label: "Resources", Icon: null },
];

const entryDays = new Set([8, 10, 12, 15, 16]);
const calRows = [[null,null,null,1,2,3,4,5,6],[7,8,9,10,11,12,13],[14,15,16,17,18,19,20],[21,22,23,24,25,26,27],[28,29,30,31]];
const calDays = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];

export default function JournalPage({ onNavigate }: JournalPageProps) {
  const [text, setText] = useState("");
  const [selectedMood, setSelectedMood] = useState<MoodKey | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [activePrompt, setActivePrompt] = useState<string | null>(null);

  const moods: { key: MoodKey; label: string }[] = [
    { key: "great",    label: "Great" },
    { key: "good",     label: "Good" },
    { key: "okay",     label: "Okay" },
    { key: "notgreat", label: "Not great" },
    { key: "difficult",label: "Difficult" },
  ];

  const toggleTag = (tag: string) =>
    setSelectedTags((p) => p.includes(tag) ? p.filter((t) => t !== tag) : [...p, tag]);

  return (
    <div style={{ minHeight: "100vh", background: "#F5F4FF", fontFamily: "Nunito, sans-serif" }}>
      {/* Top Nav */}
      <nav style={{ background: "#fff", borderBottom: "1px solid #E8E6F5", padding: "0 32px", display: "flex", alignItems: "center", height: 60, gap: 28, position: "sticky", top: 0, zIndex: 20 }}>
        <span style={{ fontWeight: 900, fontSize: 26, color: "#6C5CE7", marginRight: 8 }}>Kio</span>
        {navLinks.map((n) => (
          <button key={n.id} onClick={() => onNavigate(n.id)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14, fontWeight: n.id === "journal" ? 700 : 600, color: n.id === "journal" ? "#6C5CE7" : "#8B8BA7", borderBottom: n.id === "journal" ? "2px solid #6C5CE7" : "2px solid transparent", padding: "4px 2px", fontFamily: "Nunito, sans-serif", transition: "color 0.15s" }}>
            {n.label}
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

      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 24px 56px" }}>
        {/* Back */}
        <button onClick={() => onNavigate("home")} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 14, color: "#6C5CE7", fontWeight: 600, padding: "16px 0", fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 6 }}>
          <ArrowLeftIcon size={14} color="#6C5CE7" /> Back to Dashboard
        </button>

        {/* Hero */}
        <div style={{ background: "linear-gradient(135deg,#EEF0FF 0%,#E6FFF8 60%,#F5F0FF 100%)", borderRadius: 24, padding: "28px 32px", display: "flex", alignItems: "center", justifyContent: "space-between", overflow: "hidden", marginBottom: 24 }} className="page-enter">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 10 }}>
              <div style={{ width: 50, height: 50, background: "#EEF0FF", borderRadius: 14, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <JournalIcon size={26} color="#6C5CE7" />
              </div>
              <div>
                <h1 style={{ fontSize: 28, fontWeight: 900, color: "#1A1A3E", margin: 0 }}>My Journal</h1>
                <p style={{ fontSize: 14, color: "#8B8BA7", margin: 0 }}>A space for your thoughts, feelings and everything in between.</p>
              </div>
            </div>
            <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
              {[
                { Icon: PenIcon,      color: "#6C5CE7", val: "12",        label: "entries" },
                { Icon: CalendarIcon, color: "#00997A", val: "8",         label: "this month" },
                { Icon: LeafIcon,     color: "#D97706", val: "Keep going",label: "Small steps matter" },
              ].map((s, i) => (
                <div key={i} style={{ background: "#fff", borderRadius: 14, padding: "10px 16px", display: "flex", alignItems: "center", gap: 8 }}>
                  <s.Icon size={18} color={s.color} />
                  <div>
                    <div style={{ fontWeight: 800, fontSize: 15, color: "#1A1A3E" }}>{s.val}</div>
                    <div style={{ fontSize: 11, color: "#8B8BA7" }}>{s.label}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
            <p style={{ fontFamily: "Caveat, cursive", fontSize: 18, color: "#6C5CE7", textAlign: "right", margin: "0 0 -8px", lineHeight: 1.35 }}>A safe space<br />Brighter days ahead ♡</p>
            <Mascot size={120} />
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 20 }}>
          {/* Left */}
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>

            {/* Mood */}
            <div style={{ background: "#fff", borderRadius: 20, padding: "20px 24px", border: "1px solid #E8E6F5" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <SparkleIcon size={19} color="#6C5CE7" />
                <span style={{ fontWeight: 700, fontSize: 16, color: "#1A1A3E" }}>How are you feeling today?</span>
              </div>
              <p style={{ fontSize: 13, color: "#8B8BA7", margin: "0 0 16px" }}>There's no right or wrong answer. Just how you feel right now.</p>
              <div style={{ display: "flex", gap: 18 }}>
                {moods.map((m) => (
                  <button key={m.key} onClick={() => setSelectedMood(m.key)} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 7, background: "none", border: "none", cursor: "pointer", transition: "transform 0.15s", transform: selectedMood === m.key ? "scale(1.1)" : "scale(1)" }}>
                    <MoodFace mood={m.key} size={50} selected={selectedMood === m.key} />
                    <span style={{ fontSize: 12, fontWeight: 600, color: "#1A1A3E" }}>{m.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Write */}
            <div style={{ background: "#fff", borderRadius: 20, padding: "20px 24px", border: "1px solid #E8E6F5" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <PenIcon size={19} color="#6C5CE7" />
                  <span style={{ fontWeight: 700, fontSize: 16, color: "#1A1A3E" }}>What would you like to write about?</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, background: "#EEF0FF", borderRadius: 10, padding: "6px 12px", fontSize: 12, fontWeight: 600, color: "#6C5CE7", cursor: "pointer" }}>
                  <LockIcon size={13} color="#6C5CE7" /> Private to you ▾
                </div>
              </div>
              <p style={{ fontSize: 13, color: "#8B8BA7", margin: "0 0 14px" }}>Write freely — your thoughts, your feelings, your day, or anything on your mind.</p>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={activePrompt || "Start writing..."}
                maxLength={2000}
                style={{ width: "100%", minHeight: 140, border: "none", outline: "none", resize: "vertical", fontSize: 15, color: "#1A1A3E", fontFamily: "Nunito, sans-serif", lineHeight: 1.65, padding: 0, background: "transparent" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, paddingTop: 12, borderTop: "1px solid #F0EFF9" }}>
                <span style={{ fontSize: 12, color: "#8B8BA7" }}>There's no right or wrong way to journal. This is your space.</span>
                <span style={{ fontSize: 12, color: "#8B8BA7" }}>{text.length}/2000</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
                <TagIcon size={15} color="#8B8BA7" />
                <span style={{ fontSize: 13, color: "#8B8BA7" }}>Add a tag</span>
                {tags.map((tag) => (
                  <button key={tag} onClick={() => toggleTag(tag)} style={{ background: selectedTags.includes(tag) ? "#6C5CE7" : "#EEF0FF", color: selectedTags.includes(tag) ? "#fff" : "#6C5CE7", border: "none", borderRadius: 20, padding: "4px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "Nunito", transition: "background 0.15s" }}>
                    {tag}
                  </button>
                ))}
                <button style={{ marginLeft: "auto", background: "#6C5CE7", color: "#fff", border: "none", borderRadius: 14, padding: "10px 22px", fontSize: 14, fontWeight: 700, cursor: "pointer", fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 6 }}>
                  Save entry <ArrowRightIcon size={14} color="#fff" />
                </button>
              </div>
            </div>

            {/* Prompts */}
            <div style={{ background: "#fff", borderRadius: 20, padding: "20px 24px", border: "1px solid #E8E6F5" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <SparkleIcon size={19} color="#6C5CE7" />
                  <span style={{ fontWeight: 700, fontSize: 16, color: "#1A1A3E" }}>Not sure where to start?</span>
                </div>
                <button style={{ fontSize: 13, color: "#6C5CE7", fontWeight: 700, background: "none", border: "none", cursor: "pointer", fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 4 }}>
                  See all prompts <ArrowRightIcon size={13} color="#6C5CE7" />
                </button>
              </div>
              <p style={{ fontSize: 13, color: "#8B8BA7", margin: "0 0 16px" }}>Try a prompt, or write about anything on your mind.</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {prompts.map((p) => {
                  const active = activePrompt === p.sub;
                  return (
                    <button
                      key={p.title}
                      onClick={() => setActivePrompt(active ? null : p.sub)}
                      style={{ background: active ? "#6C5CE7" : p.bg, border: active ? "none" : "1px solid #E8E6F5", borderRadius: 16, padding: "16px", textAlign: "left", cursor: "pointer", fontFamily: "Nunito", transition: "transform 0.15s" }}
                      onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.02)")}
                      onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
                    >
                      <div style={{ width: 36, height: 36, borderRadius: 10, background: active ? "rgba(255,255,255,0.2)" : "#fff", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 10 }}>
                        <p.Icon size={20} color={active ? "#fff" : p.iconColor} />
                      </div>
                      <div style={{ fontWeight: 700, fontSize: 14, color: active ? "#fff" : "#1A1A3E" }}>{p.title}</div>
                      <div style={{ fontSize: 12, color: active ? "rgba(255,255,255,0.75)" : "#8B8BA7", marginTop: 3 }}>{p.sub}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Recent entries */}
            <div style={{ background: "#fff", borderRadius: 20, padding: "20px 24px", border: "1px solid #E8E6F5" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <JournalIcon size={19} color="#6C5CE7" />
                  <span style={{ fontWeight: 700, fontSize: 16, color: "#1A1A3E" }}>Recent entries</span>
                </div>
                <button style={{ fontSize: 13, color: "#6C5CE7", fontWeight: 700, background: "none", border: "none", cursor: "pointer", fontFamily: "Nunito", display: "flex", alignItems: "center", gap: 4 }}>
                  View all <ArrowRightIcon size={13} color="#6C5CE7" />
                </button>
              </div>
              <p style={{ fontSize: 13, color: "#8B8BA7", margin: "0 0 16px" }}>Continue your journey. You can always come back to your thoughts.</p>
              {recentEntries.map((e, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 14, padding: "13px 0", borderBottom: i < recentEntries.length - 1 ? "1px solid #F0EFF9" : "none" }}>
                  <div style={{ textAlign: "center", minWidth: 36 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: "#8B8BA7", letterSpacing: 0.5 }}>{e.date[0]}</div>
                    <div style={{ fontSize: 18, fontWeight: 800, color: "#1A1A3E", lineHeight: 1.1 }}>{e.date[1]}</div>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 14, color: "#1A1A3E" }}>{e.title}</div>
                    <div style={{ fontSize: 12, color: "#8B8BA7", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.preview}</div>
                  </div>
                  <MoodFace mood={e.mood} size={32} />
                  <div style={{ display: "flex", gap: 5, flexShrink: 0 }}>
                    {e.tags.map((t) => (
                      <span key={t} style={{ background: "#EEF0FF", color: "#6C5CE7", borderRadius: 20, padding: "2px 10px", fontSize: 11, fontWeight: 600 }}>{t}</span>
                    ))}
                  </div>
                  <MoreVertIcon size={18} color="#C8C4E0" />
                </div>
              ))}
            </div>
          </div>

          {/* Right sidebar */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Calendar */}
            <div style={{ background: "#fff", borderRadius: 20, padding: "20px", border: "1px solid #E8E6F5" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
                <span style={{ fontWeight: 700, fontSize: 15, color: "#1A1A3E" }}>September 2026</span>
                <div style={{ display: "flex", gap: 6 }}>
                  {["‹","›"].map((ch) => (
                    <button key={ch} style={{ background: "#F0EFF9", border: "none", borderRadius: 8, width: 28, height: 28, cursor: "pointer", fontSize: 15, display: "flex", alignItems: "center", justifyContent: "center", color: "#6C5CE7" }}>{ch}</button>
                  ))}
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(7,1fr)", gap: 2, textAlign: "center" }}>
                {calDays.map((d) => (
                  <div key={d} style={{ fontSize: 10, color: "#8B8BA7", fontWeight: 600, paddingBottom: 8 }}>{d}</div>
                ))}
                {calRows.flat().map((day, i) => (
                  <div key={i} style={{ width: 30, height: 30, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: day === 16 ? 800 : 500, background: day === 16 ? "#6C5CE7" : "transparent", color: day === 16 ? "#fff" : day ? "#1A1A3E" : "transparent", cursor: day ? "pointer" : "default", position: "relative", margin: "0 auto" }}>
                    {day}
                    {day && entryDays.has(day) && day !== 16 && (
                      <span style={{ position: "absolute", bottom: 2, left: "50%", transform: "translateX(-50%)", width: 4, height: 4, borderRadius: "50%", background: [8,12].includes(day) ? "#6C5CE7" : "#fd79a8" }} />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Quote */}
            <div style={{ background: "#EEF0FF", borderRadius: 20, padding: "18px 20px", border: "1px solid #E8E6F5" }}>
              <LeafIcon size={22} color="#6C5CE7" />
              <p style={{ fontWeight: 700, fontSize: 14, color: "#1A1A3E", margin: "8px 0 6px" }}>"Progress, not perfection."</p>
              <p style={{ fontSize: 12, color: "#8B8BA7", margin: 0 }}>Every thought you write is a step towards a better you.</p>
            </div>

            {/* Stats */}
            <div style={{ background: "#fff", borderRadius: 20, padding: "18px 20px", border: "1px solid #E8E6F5" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                <BarChartIcon size={19} color="#6C5CE7" />
                <span style={{ fontWeight: 700, fontSize: 15, color: "#1A1A3E" }}>Your journal stats</span>
              </div>
              {[
                { Icon: PenIcon,    color: "#6C5CE7", val: "12", label: "Total entries" },
                { Icon: LeafIcon,   color: "#00997A", val: "8",  label: "This month" },
                { Icon: FlameIcon,  color: "#F76707", val: "3",  label: "Weeks in a row" },
              ].map((s, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                  <div style={{ width: 32, height: 32, borderRadius: 9, background: "#F5F4FF", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <s.Icon size={17} color={s.color} />
                  </div>
                  <span style={{ fontWeight: 800, fontSize: 18, color: "#1A1A3E" }}>{s.val}</span>
                  <span style={{ fontSize: 13, color: "#8B8BA7" }}>{s.label}</span>
                </div>
              ))}
            </div>

            {/* Safety */}
            <div style={{ background: "#F5F0FF", borderRadius: 20, padding: "18px 20px", border: "1px solid #E8E6F5" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <ShieldIcon size={20} color="#6C5CE7" />
                <LockIcon size={18} color="#A29BFE" />
              </div>
              <p style={{ fontWeight: 700, fontSize: 14, color: "#1A1A3E", margin: "0 0 8px" }}>Your thoughts are safe here</p>
              <p style={{ fontSize: 12, color: "#8B8BA7", margin: "0 0 12px", lineHeight: 1.55 }}>Your journal is personal. Kio may use automated safety checks to help keep you safe. It's not shared with other students, parents, or counselors through the normal journal experience.</p>
              <button style={{ fontSize: 13, color: "#6C5CE7", fontWeight: 700, background: "none", border: "none", cursor: "pointer", fontFamily: "Nunito", padding: 0, display: "flex", alignItems: "center", gap: 4 }}>
                Learn more <ArrowRightIcon size={13} color="#6C5CE7" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function AvatarCircle() {
  return (
    <div style={{ width: 34, height: 34, borderRadius: "50%", background: "linear-gradient(135deg,#a29bfe,#fd79a8)", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
      <svg width="34" height="34" viewBox="0 0 34 34" fill="none">
        <circle cx="17" cy="14" r="6" fill="#fff" opacity="0.9" />
        <ellipse cx="17" cy="28" rx="10" ry="7" fill="#fff" opacity="0.9" />
      </svg>
    </div>
  );
}
