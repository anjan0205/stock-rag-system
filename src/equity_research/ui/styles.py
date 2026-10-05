"""The look. All CSS for the dashboard lives here as one injectable string.

A dark "glass + neon" theme: an animated aurora background, frosted glass
cards, gradient/glow accents, a scrolling ticker tape, and pill tabs.
"""
from __future__ import annotations

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@600;700&display=swap');

:root {
  --bg:#0a0c12; --violet:#7c5cff; --cyan:#38bdf8; --mint:#2ce6a8; --coral:#ff5d73;
  --glass:rgba(255,255,255,0.045); --glass-brd:rgba(255,255,255,0.09); --ink:#e6e9ef; --sub:#8a93a6;
}

/* ---- base ---- */
html, body, [class*="css"], .stApp, .stMarkdown, input, textarea, button, select {
  font-family:'Inter', system-ui, sans-serif;
}
.stApp { background:var(--bg); color:var(--ink); }

/* animated aurora behind everything */
.stApp::before {
  content:""; position:fixed; inset:-20% -20% -20% -20%; z-index:0; pointer-events:none;
  background:
    radial-gradient(38% 44% at 18% 22%, rgba(124,92,255,0.32), transparent 60%),
    radial-gradient(34% 40% at 82% 18%, rgba(56,189,248,0.24), transparent 60%),
    radial-gradient(46% 50% at 70% 88%, rgba(44,230,168,0.18), transparent 62%),
    radial-gradient(40% 46% at 26% 82%, rgba(255,93,115,0.14), transparent 60%);
  filter:blur(38px) saturate(120%);
  animation:drift 22s ease-in-out infinite alternate;
}
@keyframes drift {
  0%   { transform:translate3d(0,0,0) scale(1); }
  50%  { transform:translate3d(2%, -2%,0) scale(1.06); }
  100% { transform:translate3d(-2%,2%,0) scale(1.03); }
}
/* hide Streamlit's top chrome (Deploy button + running/status toolbar) so the
   scrolling ticker tape sits at the very top */
header[data-testid="stHeader"] { display:none !important; }
[data-testid="stToolbar"] { display:none !important; }
[data-testid="stDecoration"] { display:none !important; }

.block-container { position:relative; z-index:1; padding-top:1.6rem; padding-bottom:2rem; max-width:1440px; }

/* headings */
h1,h2,h3 { font-family:'Space Grotesk','Inter',sans-serif !important; letter-spacing:-0.01em; }
h1 {
  background:linear-gradient(92deg,#fff 0%, #c9c2ff 40%, #8fd8ff 75%);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
}

/* ---- ticker tape ---- */
.tape {
  position:relative; z-index:2; overflow:hidden; white-space:nowrap;
  border:1px solid rgba(124,92,255,0.35); border-radius:14px;
  background:rgba(23,27,38,0.85); backdrop-filter:blur(10px);
  padding:10px 0; margin:0 0 14px; min-height:44px;
  box-shadow:0 4px 20px rgba(0,0,0,0.25);
}
.tape-track {
  display:inline-block; white-space:nowrap; will-change:transform;
  animation:tape 42s linear infinite;
}
.tape:hover .tape-track { animation-play-state:paused; }
@keyframes tape { 0%{transform:translateX(0);} 100%{transform:translateX(-50%);} }
.tape-item { display:inline-flex; align-items:baseline; gap:8px; margin:0 26px; font-size:.92rem; }
.tape-sym { font-weight:700; color:var(--ink); letter-spacing:.02em; }
.tape-px  { font-family:'JetBrains Mono',monospace; color:var(--sub); }
.tape-chg { font-family:'JetBrains Mono',monospace; font-weight:700; }

/* ---- glass hero ---- */
.hero-wrap { position:relative; z-index:1; border-radius:22px; padding:2px; margin-bottom:12px; }
.hero-wrap::before {
  content:""; position:absolute; inset:0; border-radius:22px; padding:1px;
  background:conic-gradient(from var(--a,0deg), var(--violet), var(--cyan), var(--mint), var(--violet));
  -webkit-mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite:xor; mask-composite:exclude; opacity:.65;
  animation:spin 8s linear infinite;
}
@property --a { syntax:'<angle>'; inherits:false; initial-value:0deg; }
@keyframes spin { to { --a:360deg; } }
.hero-card {
  position:relative; border-radius:21px; padding:22px 26px;
  background:linear-gradient(160deg, rgba(23,27,38,0.92), rgba(14,16,24,0.92));
  backdrop-filter:blur(16px);
}
.hero-top { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }
.hero-name { font-family:'Space Grotesk',sans-serif; font-size:1.7rem; font-weight:700; line-height:1.1; }
.hero-sub  { color:var(--sub); font-size:.85rem; margin-top:6px; }
.hero-price-row { margin-top:16px; display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; }
.hero-price {
  font-family:'JetBrains Mono',monospace; font-size:2.9rem; font-weight:700; line-height:1;
  text-shadow:0 0 26px rgba(124,92,255,0.35);
}
.hero-chg { font-family:'JetBrains Mono',monospace; font-size:1.1rem; font-weight:700; padding:4px 10px; border-radius:10px; }
.hero-chg.up   { color:var(--mint);  background:rgba(44,230,168,0.10); }
.hero-chg.down { color:var(--coral); background:rgba(255,93,115,0.10); }
.hero-chg.flat { color:var(--sub);   background:rgba(255,255,255,0.05); }

/* chips */
.chip { display:inline-block; padding:3px 11px; border-radius:999px; font-size:.7rem; font-weight:600;
  margin-right:6px; background:rgba(255,255,255,0.05); color:#b8c0d0; border:1px solid var(--glass-brd); }
.chip.open   { background:rgba(44,230,168,0.12); color:#7ff0c8; border-color:rgba(44,230,168,0.35);
  box-shadow:0 0 14px rgba(44,230,168,0.25); }
.chip.closed { background:rgba(255,93,115,0.12); color:#ff9aa8; border-color:rgba(255,93,115,0.35); }

/* ---- metric cards ---- */
[data-testid="stMetric"] {
  background:var(--glass); border:1px solid var(--glass-brd); border-radius:16px; padding:16px 18px;
  backdrop-filter:blur(10px); transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
[data-testid="stMetric"]:hover {
  transform:translateY(-3px); border-color:rgba(124,92,255,0.5);
  box-shadow:0 10px 30px rgba(124,92,255,0.18);
}
[data-testid="stMetricLabel"] { opacity:.7; font-size:.78rem; text-transform:uppercase; letter-spacing:.05em; }
[data-testid="stMetricValue"] { font-family:'JetBrains Mono',monospace; }

/* ---- buttons ---- */
.stButton > button {
  border:1px solid transparent; border-radius:12px; font-weight:600; color:#fff;
  background:linear-gradient(92deg, var(--violet), #5b8dff); transition:all .18s ease;
  box-shadow:0 6px 20px rgba(124,92,255,0.28);
}
.stButton > button:hover { transform:translateY(-2px); box-shadow:0 10px 30px rgba(124,92,255,0.45); filter:brightness(1.08); }
.stButton > button:disabled { background:rgba(255,255,255,0.06); color:var(--sub); box-shadow:none; }

/* ---- tabs (pills) ---- */
.stTabs [data-baseweb="tab-list"] { gap:8px; border-bottom:none; }
.stTabs [data-baseweb="tab"] {
  border-radius:12px; padding:9px 18px; background:var(--glass); border:1px solid var(--glass-brd);
}
.stTabs [aria-selected="true"] {
  background:linear-gradient(92deg, rgba(124,92,255,0.28), rgba(56,189,248,0.22)) !important;
  border-color:rgba(124,92,255,0.55) !important; box-shadow:0 0 18px rgba(124,92,255,0.25);
}

/* sidebar + inputs */
section[data-testid="stSidebar"] { background:rgba(10,12,18,0.72); backdrop-filter:blur(14px);
  border-right:1px solid var(--glass-brd); }
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
  background:var(--glass) !important; border-radius:10px !important; border:1px solid var(--glass-brd) !important;
}
[data-testid="stChatInput"] { border-radius:14px; border:1px solid var(--glass-brd); background:var(--glass); }

/* status/expander glass */
[data-testid="stExpander"], .stAlert { border-radius:14px; }

/* scrollbar */
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-thumb { background:rgba(124,92,255,0.35); border-radius:10px; }
::-webkit-scrollbar-thumb:hover { background:rgba(124,92,255,0.55); }
::-webkit-scrollbar-track { background:transparent; }
</style>
"""
