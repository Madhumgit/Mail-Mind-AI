import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Mail, Briefcase, GraduationCap, Calendar, ShieldAlert, Inbox,
  RefreshCw, Trash2, CheckCheck, Clock, Wifi, WifiOff,
  X, Search, Settings, AlertCircle, MessageSquare,
  Copy, Check, Zap, ChevronDown, Menu
} from "lucide-react";

const isCapacitor = typeof window !== "undefined" && window.Capacitor !== undefined;
const isLocalDev  = !isCapacitor && (
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
);
const API = isLocalDev
  ? "http://localhost:5000/api"
  : "https://mail-mind-ai.onrender.com/api";

const USER_ID_KEY = "mailmind_user_id";

const CATS = {
  All:        { icon: Inbox,         color: "#6366f1", bg: "#eef2ff", label: "All"         },
  Job:        { icon: Briefcase,     color: "#0ea5e9", bg: "#f0f9ff", label: "Jobs"         },
  Internship: { icon: GraduationCap, color: "#8b5cf6", bg: "#f5f3ff", label: "Internships" },
  Meeting:    { icon: Calendar,      color: "#10b981", bg: "#ecfdf5", label: "Meetings"     },
  Spam:       { icon: ShieldAlert,   color: "#ef4444", bg: "#fef2f2", label: "Spam"         },
  Other:      { icon: Mail,          color: "#f59e0b", bg: "#fffbeb", label: "Other"        },
};

const PRI_COLOR = { High: "#ef4444", Medium: "#f59e0b", Low: "#10b981" };
const PRI_BG    = { High: "#fef2f2", Medium: "#fffbeb", Low: "#ecfdf5" };

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );
  useEffect(() => {
    const fn = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);
  return isCapacitor || isMobile;
}

export default function App() {
  const isMobile = useIsMobile();

  const [userId,           setUserId]           = useState(() => localStorage.getItem(USER_ID_KEY) || "");
  const [emails,           setEmails]           = useState([]);
  const [stats,            setStats]            = useState({});
  const [activeTab,        setActiveTab]        = useState("All");
  const [selectedEmail,    setSelectedEmail]    = useState(null);
  const [loading,          setLoading]          = useState(false);
  const [fetching,         setFetching]         = useState(false);
  const [connected,        setConnected]        = useState(null);
  const [searchQuery,      setSearchQuery]      = useState("");
  const [toast,            setToast]            = useState(null);
  const [showSidebar,      setShowSidebar]      = useState(false);
  const [showSettings,     setShowSettings]     = useState(false);
  const [settingsEmail,    setSettingsEmail]    = useState("");
  const [settingsPassword, setSettingsPassword] = useState("");
  const [settingsMsg,      setSettingsMsg]      = useState("");
  const [savingSettings,   setSavingSettings]   = useState(false);
  const [showPassword,     setShowPassword]     = useState(false);
  const [smartReplies,     setSmartReplies]     = useState({});
  const [loadingReplies,   setLoadingReplies]   = useState({});
  const [copiedReply,      setCopiedReply]      = useState(null);

  const showToast = (msg, type = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    if (userId) localStorage.setItem(USER_ID_KEY, userId);
  }, [userId]);

  const withUser = (params = {}) => ({ ...params, user_id: userId });

  // ── Data loaders ──────────────────────────────────────────────────────────────
  const loadEmails = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      // ✅ FIX: limit increased to 500
      const params = withUser({ limit: 500 });
      if (activeTab !== "All") params.category = activeTab;
      const { data } = await axios.get(`${API}/emails`, { params });
      setEmails(data.emails || []);
    } catch {
      showToast("Failed to load emails", "error");
    }
    setLoading(false);
  }, [activeTab, userId]);

  const loadStats = useCallback(async () => {
    if (!userId) return;
    try {
      const { data } = await axios.get(`${API}/stats`, { params: withUser() });
      setStats(data);
    } catch {}
  }, [userId]);

  const checkConn = useCallback(async () => {
    if (!userId) { setConnected(false); return; }
    try {
      const { data } = await axios.get(`${API}/connection/test`, { params: withUser() });
      setConnected(data.connected);
    } catch {
      setConnected(false);
    }
  }, [userId]);

  useEffect(() => {
    if (userId) {
      loadEmails();
      loadStats();
      checkConn();
      setSettingsEmail(userId);
    } else {
      setShowSettings(true);
    }
  }, [userId]);

  useEffect(() => { loadEmails(); }, [loadEmails]);

  // ── Actions ───────────────────────────────────────────────────────────────────
  const fetchNow = async () => {
    if (!connected) { setShowSettings(true); showToast("Configure Gmail first", "error"); return; }
    setFetching(true);
    try {
      const { data } = await axios.post(`${API}/emails/fetch`, { user_id: userId });
      showToast(data.message, "success");
      // ✅ Auto-reload emails after 60s (background fetch takes time)
      setTimeout(async () => {
        await loadEmails();
        await loadStats();
      }, 60000);
    } catch {
      showToast("Fetch failed", "error");
    }
    setFetching(false);
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    await axios.delete(`${API}/emails/${id}`);
    setEmails(prev => prev.filter(em => em.id !== id));
    if (selectedEmail?.id === id) setSelectedEmail(null);
    showToast("Email removed", "info");
    loadStats();
  };

  const handleMarkRead = async (id, e) => {
    e.stopPropagation();
    await axios.patch(`${API}/emails/${id}/read`);
    setEmails(prev => prev.map(em => em.id === id ? { ...em, is_read: 1 } : em));
  };

  const handleSaveSettings = async () => {
    if (!settingsEmail || !settingsPassword) {
      setSettingsMsg("❌ Both fields required");
      return;
    }
    setSavingSettings(true);
    setSettingsMsg("");
    try {
      const { data } = await axios.post(`${API}/settings`, {
        email:        settingsEmail.trim().toLowerCase(),
        app_password: settingsPassword,
        user_id:      settingsEmail.trim().toLowerCase(),
      });
      if (data.success) {
        const newUserId = settingsEmail.trim().toLowerCase();
        setUserId(newUserId);
        setSettingsMsg("✅ Saved!");
        setTimeout(async () => {
          setShowSettings(false);
          setSettingsMsg("");
          await checkConn();
          showToast("Gmail connected!", "success");
        }, 1200);
      } else {
        setSettingsMsg(`❌ ${data.error}`);
      }
    } catch {
      setSettingsMsg("❌ Failed to save");
    }
    setSavingSettings(false);
  };

  const fetchSmartReplies = async (em) => {
    if (smartReplies[em.id]) return;
    setLoadingReplies(prev => ({ ...prev, [em.id]: true }));
    try {
      const { data } = await axios.post(`${API}/smart-replies`, {
        subject: em.subject, body: em.body,
        category: em.category, sender: em.sender,
      });
      if (data.success) setSmartReplies(prev => ({ ...prev, [em.id]: data.replies }));
    } catch {}
    setLoadingReplies(prev => ({ ...prev, [em.id]: false }));
  };

  const handleSelectEmail = (em) => {
    const isSelected = selectedEmail?.id === em.id;
    setSelectedEmail(isSelected ? null : em);
    if (!isSelected) fetchSmartReplies(em);
  };

  const handleCopyReply = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedReply(idx);
    showToast("Copied!", "success");
    setTimeout(() => setCopiedReply(null), 2000);
  };

  const filtered = emails.filter(em => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      em.subject?.toLowerCase().includes(q) ||
      em.sender?.toLowerCase().includes(q) ||
      em.summary?.toLowerCase().includes(q)
    );
  });

  // ── SETTINGS MODAL ────────────────────────────────────────────────────────────
  const SettingsModal = () => (
    <div
      style={{ position:"fixed", inset:0, background:"rgba(15,23,42,0.5)", display:"grid",
               placeItems:"center", zIndex:9999, backdropFilter:"blur(4px)" }}
      onClick={() => { if (userId) setShowSettings(false); }}
    >
      <div
        style={{ background:"#fff", borderRadius:16, width: isMobile ? "92vw" : 480,
                 padding:28, boxShadow:"0 24px 64px rgba(0,0,0,0.2)" }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:20 }}>
          <div style={{ display:"flex", alignItems:"center", gap:10, fontSize:17, fontWeight:700, color:"#1e293b" }}>
            <div style={{ width:34, height:34, background:"#eef2ff", borderRadius:9, display:"grid", placeItems:"center" }}>
              <Settings size={16} color="#6366f1"/>
            </div>
            Gmail Settings
          </div>
          {userId && (
            <button onClick={() => setShowSettings(false)}
              style={{ background:"transparent", border:"none", cursor:"pointer", padding:4 }}>
              <X size={18} color="#94a3b8"/>
            </button>
          )}
        </div>

        <div style={{ background:"#f8fafc", border:"1px solid #e2e8f0", borderRadius:10,
                      padding:"14px 16px", marginBottom:18 }}>
          <div style={{ fontSize:12, color:"#6366f1", fontWeight:700, marginBottom:8 }}>
            🔐 How to get App Password
          </div>
          {[
            "Go to myaccount.google.com/security",
            "Enable 2-Step Verification",
            "Go to myaccount.google.com/apppasswords",
            "Create password named 'MailMind'",
            "Copy the 16-character password",
          ].map((s, i) => (
            <div key={i} style={{ display:"flex", gap:8, fontSize:12, color:"#64748b", marginBottom:4 }}>
              <span style={{ width:18, height:18, background:"#eef2ff", color:"#6366f1", borderRadius:"50%",
                             display:"inline-flex", alignItems:"center", justifyContent:"center",
                             fontSize:10, fontWeight:700, flexShrink:0 }}>{i + 1}</span>
              {s}
            </div>
          ))}
        </div>

        <div style={{ display:"flex", flexDirection:"column", gap:14 }}>
          <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
            <label htmlFor="settings-email" style={{ fontSize:12, color:"#475569", fontWeight:600 }}>
              Gmail Address
            </label>
            <input
              id="settings-email" name="email" type="email" autoComplete="email"
              value={settingsEmail} onChange={e => setSettingsEmail(e.target.value)}
              placeholder="you@gmail.com"
              style={{ background:"#f8fafc", border:"1px solid #e2e8f0", borderRadius:9,
                       padding:"11px 14px", color:"#1e293b", fontSize:14, outline:"none", width:"100%" }}
            />
          </div>

          <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
            <label htmlFor="settings-password" style={{ fontSize:12, color:"#475569", fontWeight:600 }}>
              App Password
            </label>
            <div style={{ position:"relative" }}>
              <input
                id="settings-password" name="app_password"
                type={showPassword ? "text" : "password"} autoComplete="current-password"
                value={settingsPassword} onChange={e => setSettingsPassword(e.target.value)}
                placeholder="xxxx xxxx xxxx xxxx"
                style={{ background:"#f8fafc", border:"1px solid #e2e8f0", borderRadius:9,
                         padding:"11px 14px", paddingRight:60, color:"#1e293b",
                         fontSize:14, outline:"none", width:"100%" }}
              />
              <button onClick={() => setShowPassword(!showPassword)}
                style={{ position:"absolute", right:12, top:"50%", transform:"translateY(-50%)",
                         background:"transparent", border:"none", color:"#6366f1",
                         fontSize:12, fontWeight:600, cursor:"pointer" }}>
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            <div style={{ fontSize:11, color:"#94a3b8" }}>⚠️ Not your Gmail login password</div>
          </div>

          {settingsMsg && (
            <div style={{ fontSize:13, padding:"10px 12px", borderRadius:8, fontWeight:500,
                          background: settingsMsg.includes("✅") ? "#dcfce7" : "#fee2e2",
                          color:      settingsMsg.includes("✅") ? "#166534" : "#991b1b" }}>
              {settingsMsg}
            </div>
          )}

          <button onClick={handleSaveSettings} disabled={savingSettings}
            style={{ padding:"12px 0", background:"linear-gradient(135deg,#6366f1,#8b5cf6)",
                     border:"none", borderRadius:9, color:"#fff", fontSize:14, fontWeight:700,
                     width:"100%", cursor:"pointer", opacity: savingSettings ? 0.7 : 1 }}>
            {savingSettings ? "Saving..." : "Save & Connect"}
          </button>
        </div>
      </div>
    </div>
  );

  // ── SIDEBAR ───────────────────────────────────────────────────────────────────
  const SidebarContent = () => (
    <>
      <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:24,
                    paddingBottom:18, borderBottom:"1px solid #f1f5f9" }}>
        <div style={{ width:38, height:38, borderRadius:10,
                      background:"linear-gradient(135deg,#6366f1,#8b5cf6)",
                      display:"grid", placeItems:"center", flexShrink:0 }}>
          <Mail size={18} color="#fff"/>
        </div>
        <div>
          <div style={{ fontSize:16, fontWeight:800, color:"#1e293b" }}>MailMind</div>
          <div style={{ fontSize:10, color:"#94a3b8" }}>AI Email Assistant</div>
        </div>
      </div>

      {userId && (
        <div style={{ fontSize:11, color:"#64748b", background:"#f1f5f9", borderRadius:8,
                      padding:"6px 10px", marginBottom:12, wordBreak:"break-all" }}>
          👤 {userId}
        </div>
      )}

      <div style={{ display:"flex", alignItems:"center", gap:8, padding:"8px 12px", borderRadius:10,
                    marginBottom:20,
                    background: connected ? "#dcfce7" : connected === false ? "#fee2e2" : "#f1f5f9",
                    border: `1px solid ${connected ? "#86efac" : connected === false ? "#fca5a5" : "#e2e8f0"}` }}>
        {connected === null ? <Clock size={13} color="#94a3b8"/>
          : connected ? <Wifi size={13} color="#16a34a"/>
          : <WifiOff size={13} color="#dc2626"/>}
        <span style={{ fontSize:12, flex:1, fontWeight:500,
                       color: connected ? "#16a34a" : connected === false ? "#dc2626" : "#64748b" }}>
          {connected === null ? "Checking..." : connected ? "Gmail Connected" : "Not Connected"}
        </span>
        {!connected && connected !== null && (
          <button onClick={() => setShowSettings(true)}
            style={{ fontSize:11, color:"#6366f1", background:"#eef2ff", border:"none",
                     borderRadius:5, padding:"2px 8px", fontWeight:600, cursor:"pointer" }}>
            Setup
          </button>
        )}
      </div>

      <div style={{ fontSize:10, color:"#94a3b8", letterSpacing:"1px",
                    fontWeight:700, padding:"0 4px 8px" }}>MAILBOX</div>
      <nav style={{ display:"flex", flexDirection:"column", gap:2, marginBottom:20 }}>
        {Object.entries(CATS).map(([cat, cfg]) => {
          const count  = cat === "All" ? (stats.total || 0) : (stats.categories?.[cat] || 0);
          const active = activeTab === cat;
          const Icon   = cfg.icon;
          return (
            <button key={cat} onClick={() => { setActiveTab(cat); setShowSidebar(false); }}
              style={{ display:"flex", alignItems:"center", gap:10, padding:"10px 12px",
                       border:"none", borderRadius:10, fontSize:14, width:"100%", textAlign:"left",
                       cursor:"pointer", fontFamily:"inherit", transition:"all 0.15s",
                       background: active ? cfg.bg : "transparent",
                       color:      active ? cfg.color : "#475569",
                       fontWeight: active ? 600 : 400,
                       boxShadow:  active ? `inset 3px 0 0 ${cfg.color}` : "none" }}>
              <Icon size={16} color={active ? cfg.color : "#94a3b8"}/>
              <span style={{ flex:1 }}>{cfg.label}</span>
              {count > 0 && (
                <span style={{ padding:"1px 8px", borderRadius:20, fontSize:11, fontWeight:600,
                               background: active ? cfg.color : "#e2e8f0",
                               color:      active ? "#fff" : "#64748b" }}>{count}</span>
              )}
            </button>
          );
        })}
      </nav>

      <div style={{ flex:1 }}/>

      <button onClick={() => setShowSettings(true)}
        style={{ display:"flex", alignItems:"center", gap:8, width:"100%", padding:"9px 12px",
                 background:"transparent", border:"1px solid #e2e8f0", borderRadius:10,
                 color:"#94a3b8", fontSize:12, cursor:"pointer", fontFamily:"inherit" }}>
        <Settings size={14} color="#94a3b8"/> Account Settings
      </button>
    </>
  );

  // ── SMART REPLIES ─────────────────────────────────────────────────────────────
  const SmartRepliesPanel = ({ em }) => {
    const replies  = smartReplies[em.id] || [];
    const loadingR = loadingReplies[em.id];
    return (
      <>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:12 }}>
          <div style={{ width:26, height:26, background:"linear-gradient(135deg,#6366f1,#8b5cf6)",
                        borderRadius:7, display:"grid", placeItems:"center" }}>
            <Zap size={13} color="#fff"/>
          </div>
          <span style={{ fontSize:13, fontWeight:700, color:"#1e293b" }}>Smart Replies</span>
          <span style={{ fontSize:11, color:"#94a3b8", background:"#f1f5f9",
                         padding:"2px 8px", borderRadius:20 }}>AI Generated</span>
        </div>
        {loadingR ? (
          <div style={{ display:"flex", alignItems:"center", gap:8, color:"#94a3b8", fontSize:13 }}>
            <RefreshCw size={14} style={{ animation:"spin 1s linear infinite" }} color="#6366f1"/>
            Generating...
          </div>
        ) : replies.length > 0 ? (
          <div style={{ display:"flex", gap:12, flexWrap:"wrap" }}>
            {replies.map((r, idx) => (
              <div key={idx} style={{ flex:1, minWidth:200, background:"#fff",
                                      border:"1px solid #e2e8f0", borderRadius:10, padding:"12px 14px" }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8 }}>
                  <span style={{ fontSize:11, fontWeight:700, color:"#6366f1", background:"#eef2ff",
                                 padding:"2px 8px", borderRadius:20 }}>{r.label}</span>
                  <button onClick={() => handleCopyReply(r.reply, idx)}
                    style={{ display:"flex", alignItems:"center", gap:4, fontSize:11,
                             color:      copiedReply === idx ? "#10b981" : "#64748b",
                             background: copiedReply === idx ? "#dcfce7" : "#f8fafc",
                             border:`1px solid ${copiedReply === idx ? "#86efac" : "#e2e8f0"}`,
                             borderRadius:6, padding:"3px 8px", cursor:"pointer" }}>
                    {copiedReply === idx ? <Check size={11}/> : <Copy size={11}/>}
                    {copiedReply === idx ? "Copied!" : "Copy"}
                  </button>
                </div>
                <div style={{ fontSize:13, color:"#334155", lineHeight:1.7, whiteSpace:"pre-wrap",
                              background:"#f8fafc", borderRadius:6, padding:"8px 10px" }}>{r.reply}</div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display:"flex", alignItems:"center", gap:8, color:"#94a3b8", fontSize:13 }}>
            <MessageSquare size={14} color="#cbd5e1"/> No smart replies available.
          </div>
        )}
      </>
    );
  };

  // ── MOBILE CARD ───────────────────────────────────────────────────────────────
  const MobileCard = ({ em }) => {
    const cfg        = CATS[em.category] || CATS.Other;
    const Icon       = cfg.icon;
    const isSelected = selectedEmail?.id === em.id;
    const replies    = smartReplies[em.id] || [];
    const loadingR   = loadingReplies[em.id];

    return (
      <div style={{ marginBottom:8 }}>
        <div onClick={() => handleSelectEmail(em)} style={{
          background: isSelected ? "#f5f7ff" : "#fff", borderRadius:12, padding:"14px 16px",
          borderLeft:`3px solid ${isSelected ? cfg.color : "transparent"}`,
          boxShadow:"0 1px 4px rgba(0,0,0,0.06)", opacity: em.is_read ? 0.7 : 1,
        }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:6 }}>
            <div style={{ display:"flex", alignItems:"center", gap:6, flex:1, minWidth:0 }}>
              {!em.is_read && (
                <span style={{ width:7, height:7, borderRadius:"50%", background:"#6366f1",
                               flexShrink:0, display:"block" }}/>
              )}
              <span style={{ fontSize:14, fontWeight: em.is_read ? 400 : 700, color:"#1e293b",
                             overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                {em.subject || "No Subject"}
              </span>
            </div>
            <span style={{ fontSize:11, color:"#94a3b8", flexShrink:0, marginLeft:8 }}>
              {em.timestamp ? new Date(em.timestamp).toLocaleDateString([], { month:"short", day:"numeric" }) : ""}
            </span>
          </div>
          <div style={{ fontSize:12, color:"#64748b", marginBottom:4 }}>{em.sender?.split("<")[0].trim()}</div>
          <div style={{ fontSize:12, color:"#94a3b8", marginBottom:10, lineHeight:1.4 }}>{em.summary}</div>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
            <div style={{ display:"flex", gap:6 }}>
              <span style={{ fontSize:10, fontWeight:600, padding:"2px 8px", borderRadius:20,
                             background:cfg.bg, color:cfg.color, display:"flex", alignItems:"center", gap:3 }}>
                <Icon size={9}/>{em.category}
              </span>
              <span style={{ fontSize:10, fontWeight:700, padding:"2px 8px", borderRadius:20,
                             background:PRI_BG[em.priority], color:PRI_COLOR[em.priority] }}>
                {em.priority}
              </span>
            </div>
            <div style={{ display:"flex", gap:4, alignItems:"center" }}>
              {!em.is_read && (
                <button onClick={e => handleMarkRead(em.id, e)} style={iconBtn}>
                  <CheckCheck size={13} color="#10b981"/>
                </button>
              )}
              <button onClick={e => handleDelete(em.id, e)} style={iconBtn}>
                <Trash2 size={13} color="#ef4444"/>
              </button>
              <ChevronDown size={13} color="#94a3b8"
                style={{ transform: isSelected ? "rotate(180deg)" : "none", transition:"0.2s" }}/>
            </div>
          </div>
        </div>

        {isSelected && (
          <div style={{ background:"#f8fafc", border:"1px solid #e2e8f0", borderRadius:12,
                        padding:"14px 16px", marginTop:4 }}>
            <div style={{ fontSize:12, color:"#64748b", marginBottom:8, lineHeight:1.8 }}>
              <strong>From:</strong> {em.sender}<br/>
              <strong>Date:</strong> {em.timestamp ? new Date(em.timestamp).toLocaleString() : ""}
            </div>
            {em.body && (
              <div style={{ fontSize:13, color:"#334155", lineHeight:1.7, whiteSpace:"pre-wrap", marginBottom:12 }}>
                {em.body.slice(0, 600)}{em.body.length > 600 ? "..." : ""}
              </div>
            )}
            <div style={{ display:"flex", alignItems:"center", gap:6, marginBottom:10 }}>
              <div style={{ width:24, height:24, background:"linear-gradient(135deg,#6366f1,#8b5cf6)",
                            borderRadius:6, display:"grid", placeItems:"center" }}>
                <Zap size={12} color="#fff"/>
              </div>
              <span style={{ fontSize:13, fontWeight:700, color:"#1e293b" }}>Smart Replies</span>
            </div>
            {loadingR ? (
              <div style={{ display:"flex", alignItems:"center", gap:8, color:"#94a3b8", fontSize:12 }}>
                <RefreshCw size={13} style={{ animation:"spin 1s linear infinite" }} color="#6366f1"/>
                Generating...
              </div>
            ) : replies.length > 0 ? (
              <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                {replies.map((r, idx) => (
                  <div key={idx} style={{ background:"#fff", border:"1px solid #e2e8f0",
                                          borderRadius:10, padding:"10px 12px" }}>
                    <div style={{ display:"flex", justifyContent:"space-between",
                                  alignItems:"center", marginBottom:6 }}>
                      <span style={{ fontSize:11, fontWeight:700, color:"#6366f1", background:"#eef2ff",
                                     padding:"2px 8px", borderRadius:20 }}>{r.label}</span>
                      <button onClick={() => handleCopyReply(r.reply, idx)}
                        style={{ display:"flex", alignItems:"center", gap:4, fontSize:11,
                                 color:      copiedReply === idx ? "#10b981" : "#64748b",
                                 background: copiedReply === idx ? "#dcfce7" : "#f8fafc",
                                 border:`1px solid ${copiedReply === idx ? "#86efac" : "#e2e8f0"}`,
                                 borderRadius:6, padding:"3px 8px", cursor:"pointer" }}>
                        {copiedReply === idx ? <Check size={11}/> : <Copy size={11}/>}
                        {copiedReply === idx ? "Copied!" : "Copy"}
                      </button>
                    </div>
                    <div style={{ fontSize:12, color:"#334155", lineHeight:1.7, whiteSpace:"pre-wrap",
                                  background:"#f8fafc", borderRadius:6, padding:"8px 10px" }}>{r.reply}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ display:"flex", alignItems:"center", gap:6, color:"#94a3b8", fontSize:12 }}>
                <MessageSquare size={13} color="#cbd5e1"/> No smart replies available.
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // ── DESKTOP ROW ───────────────────────────────────────────────────────────────
  const DesktopRow = ({ em }) => {
    const cfg        = CATS[em.category] || CATS.Other;
    const Icon       = cfg.icon;
    const isSelected = selectedEmail?.id === em.id;

    return (
      <div>
        <div onClick={() => handleSelectEmail(em)} className="email-row" style={{
          display:"flex", alignItems:"center", padding:"14px 24px",
          borderBottom:"1px solid #f1f5f9", cursor:"pointer", gap:8,
          background: isSelected ? "#f5f7ff" : "#fff",
          borderLeft: isSelected ? `4px solid ${cfg.color}` : "4px solid transparent",
          opacity: em.is_read ? 0.65 : 1, transition:"background 0.1s",
        }}>
          <div style={{ width:10, flexShrink:0 }}>
            {!em.is_read && (
              <span style={{ width:8, height:8, borderRadius:"50%", background:"#6366f1", display:"block" }}/>
            )}
          </div>
          <div style={{ flex:4, minWidth:0, paddingRight:16 }}>
            <div style={{ fontSize:14, fontWeight: em.is_read ? 400 : 700, color:"#1e293b",
                          whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
              {em.subject || "No Subject"}
            </div>
          </div>
          <div style={{ flex:2, minWidth:0, paddingRight:16 }}>
            <div style={{ fontSize:13, color:"#64748b", whiteSpace:"nowrap",
                          overflow:"hidden", textOverflow:"ellipsis" }}>
              {em.sender?.split("<")[0].trim()}
            </div>
          </div>
          <div style={{ flex:3, minWidth:0, paddingRight:16 }}>
            <div style={{ fontSize:13, color:"#94a3b8", whiteSpace:"nowrap",
                          overflow:"hidden", textOverflow:"ellipsis" }}>
              {em.summary}
            </div>
          </div>
          <div style={{ flex:1, display:"flex", justifyContent:"center" }}>
            <span style={{ display:"inline-flex", alignItems:"center", gap:4, fontSize:11,
                           fontWeight:600, padding:"3px 10px", borderRadius:20,
                           background:cfg.bg, color:cfg.color, whiteSpace:"nowrap" }}>
              <Icon size={10}/>{em.category}
            </span>
          </div>
          <div style={{ flex:1, display:"flex", justifyContent:"center" }}>
            <span style={{ fontSize:11, fontWeight:700, padding:"3px 10px", borderRadius:20,
                           background:PRI_BG[em.priority], color:PRI_COLOR[em.priority], whiteSpace:"nowrap" }}>
              {em.priority}
            </span>
          </div>
          <div style={{ flex:1, textAlign:"right", fontSize:12, color:"#94a3b8", whiteSpace:"nowrap" }}>
            {em.timestamp ? new Date(em.timestamp).toLocaleDateString([], { month:"short", day:"numeric" }) : ""}
          </div>
          <div style={{ width:70, display:"flex", justifyContent:"flex-end", gap:2, alignItems:"center" }}>
            {!em.is_read && (
              <button onClick={e => handleMarkRead(em.id, e)} style={iconBtn}>
                <CheckCheck size={14} color="#10b981"/>
              </button>
            )}
            <button onClick={e => handleDelete(em.id, e)} style={iconBtn}>
              <Trash2 size={14} color="#ef4444"/>
            </button>
            <ChevronDown size={14} color="#94a3b8"
              style={{ transform: isSelected ? "rotate(180deg)" : "none", transition:"0.2s" }}/>
          </div>
        </div>

        {isSelected && (
          <div style={{ background:"#f8fafc", borderBottom:"1px solid #e2e8f0",
                        borderLeft:`4px solid ${cfg.color}`, padding:"18px 24px 20px 42px" }}>
            <div style={{ fontSize:13, color:"#64748b", marginBottom:12, lineHeight:1.8 }}>
              <strong style={{ color:"#475569" }}>From:</strong> {em.sender} &nbsp;&nbsp;
              <strong style={{ color:"#475569" }}>Date:</strong>{" "}
              {em.timestamp ? new Date(em.timestamp).toLocaleString() : ""}
            </div>
            {em.body && (
              <div style={{ fontSize:14, color:"#334155", lineHeight:1.9,
                            whiteSpace:"pre-wrap", marginBottom:16 }}>
                {em.body.slice(0, 1000)}{em.body.length > 1000 ? "..." : ""}
              </div>
            )}
            <SmartRepliesPanel em={em}/>
          </div>
        )}
      </div>
    );
  };

  // ── GLOBAL STYLES ─────────────────────────────────────────────────────────────
  const GlobalStyles = () => (
    <style>{`
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      * { box-sizing:border-box; margin:0; padding:0; }
      html,body,#root { height:100%; overflow:hidden; }
      body { font-family:'Inter',sans-serif; background:#f1f5f9; }
      ::-webkit-scrollbar { width:5px; }
      ::-webkit-scrollbar-track { background:#f1f5f9; }
      ::-webkit-scrollbar-thumb { background:#cbd5e1; border-radius:10px; }
      @keyframes spin { to { transform:rotate(360deg); } }
      @keyframes fadeIn { from { opacity:0; transform:translateY(-6px); } to { opacity:1; transform:translateY(0); } }
      input::placeholder { color:#94a3b8; }
      button { font-family:'Inter',sans-serif; }
      .email-row:hover { background:#f8f9ff !important; }
    `}</style>
  );

  const Toast = () => toast ? (
    <div style={{ position:"fixed", top:20, right:20, padding:"12px 18px", borderRadius:12,
                  fontSize:13, fontWeight:500, zIndex:99999,
                  boxShadow:"0 4px 20px rgba(0,0,0,0.12)", animation:"fadeIn 0.2s ease",
                  background: toast.type === "error" ? "#fee2e2" : toast.type === "success" ? "#dcfce7" : "#eef2ff",
                  color:      toast.type === "error" ? "#991b1b" : toast.type === "success" ? "#166534" : "#3730a3"
    }}>{toast.msg}</div>
  ) : null;

  // ── MOBILE LAYOUT ─────────────────────────────────────────────────────────────
  if (isMobile) {
    return (
      <div style={{ display:"flex", flexDirection:"column", height:"100vh",
                    background:"#f1f5f9", fontFamily:"'Inter',sans-serif", overflow:"hidden" }}>
        <GlobalStyles/>
        <Toast/>
        {showSettings && <SettingsModal/>}

        {showSidebar && (
          <div style={{ position:"fixed", inset:0, zIndex:1000 }}>
            <div style={{ position:"absolute", inset:0, background:"rgba(0,0,0,0.4)" }}
              onClick={() => setShowSidebar(false)}/>
            <div style={{ position:"absolute", left:0, top:0, bottom:0, width:"80%", maxWidth:300,
                          background:"#fff", padding:"24px 16px", overflowY:"auto",
                          display:"flex", flexDirection:"column",
                          boxShadow:"4px 0 20px rgba(0,0,0,0.15)" }}>
              <SidebarContent/>
            </div>
          </div>
        )}

        {/* Mobile header */}
        <div style={{ background:"#fff", padding:"14px 16px", display:"flex", alignItems:"center",
                      justifyContent:"space-between", borderBottom:"1px solid #e2e8f0", flexShrink:0 }}>
          <button onClick={() => setShowSidebar(true)}
            style={{ background:"transparent", border:"none", cursor:"pointer", padding:4, display:"flex" }}>
            <Menu size={22} color="#475569"/>
          </button>
          <div style={{ fontSize:17, fontWeight:800, color:"#1e293b" }}>
            {CATS[activeTab]?.label || "All Emails"}
          </div>
          <div style={{ display:"flex", gap:8 }}>
            <button onClick={() => setShowSettings(true)}
              style={{ background:"transparent", border:"none", cursor:"pointer", padding:4, display:"flex" }}>
              <Settings size={20} color="#475569"/>
            </button>
            <button onClick={fetchNow} disabled={fetching}
              style={{ background:"transparent", border:"none", cursor:"pointer", padding:4, display:"flex" }}>
              <RefreshCw size={20} color="#6366f1"
                style={{ animation: fetching ? "spin 1s linear infinite" : "none" }}/>
            </button>
          </div>
        </div>

        {/* Category tabs */}
        <div style={{ background:"#fff", borderBottom:"1px solid #e2e8f0", padding:"0 16px",
                      flexShrink:0, overflowX:"auto", display:"flex", gap:4, scrollbarWidth:"none" }}>
          {Object.entries(CATS).map(([cat, cfg]) => {
            const count  = cat === "All" ? (stats.total || 0) : (stats.categories?.[cat] || 0);
            const active = activeTab === cat;
            return (
              <button key={cat} onClick={() => setActiveTab(cat)} style={{
                display:"inline-flex", alignItems:"center", gap:5, padding:"10px 12px",
                border:"none",
                borderBottom: active ? `2px solid ${cfg.color}` : "2px solid transparent",
                background:"transparent", color: active ? cfg.color : "#94a3b8",
                fontSize:13, fontWeight: active ? 600 : 400,
                cursor:"pointer", whiteSpace:"nowrap", fontFamily:"inherit",
              }}>
                {cfg.label}
                {count > 0 && (
                  <span style={{ fontSize:11, background: active ? cfg.color : "#e2e8f0",
                                 color: active ? "#fff" : "#64748b",
                                 padding:"0 6px", borderRadius:10, fontWeight:600 }}>{count}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div style={{ padding:"12px 16px", background:"#fff",
                      borderBottom:"1px solid #f1f5f9", flexShrink:0 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8, background:"#f8fafc",
                        border:"1px solid #e2e8f0", borderRadius:10, padding:"9px 12px" }}>
            <Search size={15} color="#94a3b8"/>
            <input id="mobile-search" name="search" value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search emails..." autoComplete="off"
              style={{ background:"transparent", border:"none", color:"#1e293b",
                       fontSize:14, outline:"none", flex:1 }}/>
            {searchQuery && (
              <button onClick={() => setSearchQuery("")}
                style={{ background:"none", border:"none", cursor:"pointer", display:"flex" }}>
                <X size={13} color="#94a3b8"/>
              </button>
            )}
          </div>
        </div>

        {connected === false && (
          <div style={{ margin:"10px 16px", display:"flex", alignItems:"center", gap:8,
                        padding:"10px 14px", background:"#fffbeb", border:"1px solid #fde68a",
                        borderRadius:10, fontSize:13, color:"#92400e", flexShrink:0 }}>
            <AlertCircle size={15} color="#d97706"/>
            <span style={{ flex:1 }}>Gmail not connected.</span>
            <button onClick={() => setShowSettings(true)}
              style={{ fontSize:12, color:"#6366f1", background:"#eef2ff", border:"none",
                       borderRadius:6, padding:"3px 10px", fontWeight:600, cursor:"pointer" }}>
              Setup
            </button>
          </div>
        )}

        {/* ✅ FIX: minHeight:0 enables proper flex scrolling on mobile */}
        <div style={{ flex:1, overflowY:"auto", padding:"12px 16px", minHeight:0 }}>
          {loading ? (
            <div style={{ display:"flex", flexDirection:"column", alignItems:"center", padding:"60px 0" }}>
              <RefreshCw size={28} color="#cbd5e1" style={{ animation:"spin 1s linear infinite" }}/>
              <p style={{ marginTop:12, color:"#94a3b8", fontSize:14 }}>Loading emails...</p>
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ display:"flex", flexDirection:"column", alignItems:"center", padding:"60px 0" }}>
              <div style={{ width:64, height:64, background:"#f1f5f9", borderRadius:"50%",
                            display:"grid", placeItems:"center" }}>
                <Inbox size={28} color="#94a3b8"/>
              </div>
              <p style={{ color:"#1e293b", fontSize:16, fontWeight:700, marginTop:14 }}>No emails found</p>
              <p style={{ color:"#94a3b8", fontSize:13, marginTop:4 }}>Tap sync to fetch emails</p>
            </div>
          ) : (
            filtered.map(em => <MobileCard key={em.id} em={em}/>)
          )}
        </div>
      </div>
    );
  }

  // ── DESKTOP LAYOUT ────────────────────────────────────────────────────────────
  return (
    <div style={{ display:"flex", height:"100vh", background:"#f1f5f9",
                  fontFamily:"'Inter',sans-serif", overflow:"hidden" }}>
      <GlobalStyles/>
      <Toast/>
      {showSettings && <SettingsModal/>}

      <aside style={{ width:280, background:"#fff", borderRight:"1px solid #e2e8f0",
                      display:"flex", flexDirection:"column", padding:"24px 16px 18px",
                      overflowY:"auto", flexShrink:0, boxShadow:"2px 0 12px rgba(0,0,0,0.04)" }}>
        <SidebarContent/>
      </aside>

      {/* ✅ FIX: main no longer overflowY auto — inner table scrolls instead */}
      <main style={{ flex:1, display:"flex", flexDirection:"column",
                     padding:"28px 36px", gap:20, minWidth:0, minHeight:0, overflow:"hidden" }}>

        {/* Top bar */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", flexShrink:0 }}>
          <div>
            <h1 style={{ fontSize:28, fontWeight:800, color:"#1e293b", letterSpacing:"-0.5px" }}>
              {CATS[activeTab]?.label || "All Emails"}
            </h1>
            <p style={{ fontSize:13, color:"#94a3b8", marginTop:3 }}>
              {filtered.length} message{filtered.length !== 1 ? "s" : ""}
              {stats.next_scheduled_fetch && (
                <span> · Auto-sync at {new Date(stats.next_scheduled_fetch)
                  .toLocaleTimeString([], { hour:"2-digit", minute:"2-digit" })}</span>
              )}
            </p>
          </div>
          <div style={{ display:"flex", gap:10, alignItems:"center" }}>
            <div style={{ display:"flex", alignItems:"center", gap:8, background:"#fff",
                          border:"1px solid #e2e8f0", borderRadius:10, padding:"10px 16px",
                          minWidth:260, boxShadow:"0 1px 4px rgba(0,0,0,0.04)" }}>
              <Search size={16} color="#94a3b8"/>
              <input id="desktop-search" name="search" value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search emails..." autoComplete="off"
                style={{ background:"transparent", border:"none", color:"#1e293b",
                         fontSize:14, outline:"none", flex:1 }}/>
              {searchQuery && (
                <button onClick={() => setSearchQuery("")}
                  style={{ background:"none", border:"none", cursor:"pointer", display:"flex" }}>
                  <X size={13} color="#94a3b8"/>
                </button>
              )}
            </div>
            <button onClick={() => setShowSettings(true)}
              style={{ width:42, height:42, background:"#fff", border:"1px solid #e2e8f0",
                       borderRadius:10, display:"grid", placeItems:"center", cursor:"pointer",
                       boxShadow:"0 1px 4px rgba(0,0,0,0.04)" }}>
              <Settings size={17} color="#64Tableb"/>
            </button>
            <button onClick={fetchNow} disabled={fetching}
              style={{ display:"flex", alignItems:"center", gap:8, padding:"10px 22px",
                       background:"linear-gradient(135deg,#6366f1,#8b5cf6)", border:"none",
                       borderRadius:10, color:"#fff", fontSize:14, fontWeight:600, cursor:"pointer",
                       boxShadow:"0 2px 10px rgba(99,102,241,0.3)", fontFamily:"inherit" }}>
              <RefreshCw size={15} color="#fff"
                style={{ animation: fetching ? "spin 1s linear infinite" : "none" }}/>
              {fetching ? "Syncing..." : "Sync Now"}
            </button>
          </div>
        </div>

        {connected === false && (
          <div style={{ display:"flex", alignItems:"center", gap:10, padding:"11px 18px",
                        background:"#fffbeb", border:"1px solid #fde68a", flexShrink:0,
                        borderRadius:12, fontSize:14, color:"#92400e" }}>
            <AlertCircle size={16} color="#d97706"/>
            <span style={{ flex:1 }}>Gmail not connected. Configure credentials to start syncing.</span>
            <button onClick={() => setShowSettings(true)}
              style={{ fontSize:12, color:"#6366f1", background:"#eef2ff", border:"none",
                       borderRadius:6, padding:"4px 14px", fontWeight:600, cursor:"pointer" }}>
              Connect →
            </button>
          </div>
        )}

        {/* ✅ FIX: email table scrolls independently — flex:1 + minHeight:0 + overflowY:auto */}
        <div style={{ background:"#fff", border:"1px solid #e2e8f0", borderRadius:14,
                      overflow:"hidden", boxShadow:"0 1px 6px rgba(0,0,0,0.04)",
                      flex:1, minHeight:0, display:"flex", flexDirection:"column" }}>

          {/* Sticky table header */}
          {filtered.length > 0 && (
            <div style={{ display:"flex", alignItems:"center", padding:"12px 24px",
                          background:"#f8fafc", borderBottom:"2px solid #e2e8f0",
                          fontSize:11, color:"#94a3b8", fontWeight:700,
                          textTransform:"uppercase", letterSpacing:"0.6px", gap:8, flexShrink:0 }}>
              <span style={{ width:10 }}/>
              <span style={{ flex:4 }}>Subject</span>
              <span style={{ flex:2 }}>From</span>
              <span style={{ flex:3 }}>Summary</span>
              <span style={{ flex:1, textAlign:"center" }}>Category</span>
              <span style={{ flex:1, textAlign:"center" }}>Priority</span>
              <span style={{ flex:1, textAlign:"right" }}>Date</span>
              <span style={{ width:70 }}/>
            </div>
          )}

          {/* ✅ Scrollable email list */}
          <div style={{ flex:1, overflowY:"auto", minHeight:0 }}>
            {loading ? (
              <div style={{ display:"flex", flexDirection:"column", alignItems:"center", padding:"80px 0" }}>
                <RefreshCw size={30} color="#cbd5e1" style={{ animation:"spin 1s linear infinite" }}/>
                <p style={{ marginTop:14, color:"#94a3b8", fontSize:15 }}>Loading emails...</p>
              </div>
            ) : filtered.length === 0 ? (
              <div style={{ display:"flex", flexDirection:"column", alignItems:"center", padding:"80px 0" }}>
                <div style={{ width:68, height:68, background:"#f1f5f9", borderRadius:"50%",
                              display:"grid", placeItems:"center" }}>
                  <Inbox size={30} color="#94a3b8"/>
                </div>
                <p style={{ color:"#1e293b", fontSize:17, fontWeight:700, marginTop:14 }}>No emails found</p>
                <p style={{ color:"#94a3b8", fontSize:14, marginTop:4 }}>
                  {connected ? 'Click "Sync Now" to fetch emails' : 'Connect Gmail to get started'}
                </p>
              </div>
            ) : (
              filtered.map(em => <DesktopRow key={em.id} em={em}/>)
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

const iconBtn = {
  width:28, height:28, background:"transparent", border:"none",
  display:"grid", placeItems:"center", borderRadius:6, cursor:"pointer"
};
