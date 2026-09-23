import React, { useState } from 'react';
import { 
  ShieldCheck, 
  Send, 
  BookOpen, 
  CheckCircle2, 
  AlertCircle, 
  LogOut, 
  FileCheck, 
  AlertTriangle, 
  Download,
  Trash2
} from 'lucide-react';

interface Source {
  source: string;
  file_name?: string;
  item_number: number;
  page_number?: number;
  question: string;
  similarity_score: number;
  content_snippet?: string;
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  role?: string;
  classification?: {
    category: string;
    subcategory: string;
    intent: string;
    depth_level: string;
    confidence_score: number;
    entities: string[];
  };
  sources?: Source[];
  evaluation?: {
    is_relevant: boolean;
    is_sufficient: boolean;
    coverage_score: number;
    action: string;
    reason: string;
  };
  latency_ms?: number;
  strategy?: string;
}

const ROLE_QUERIES: Record<string, string[]> = {
  'Bidder': [
    "What are the requirements of the client machine to access the e-Procurement site ?",
    "What is the default Date and Time format used in the System ?",
    "Can I access my eProcurement Account from a different client system ?",
    "What is the validity period of a Digital Signature Certificate ?"
  ],
  'Foreign Bidder': [
    "Can a foreign bidder or consultant get DSC from their respective country ?",
    "Can international consultant get DSC online without physical presence in India ?",
    "Whether Can I Upload BoQ with Currencies other than Indian Rupees ?",
    "Can International firm upload proposals on e-procurement portal with DSC ?"
  ],
  'Department User': [
    "What is the best practice in renewal of DSC pertaining to Department User ?",
    "What to do if Bid Opener name is not visible in bid openers list during tender creation ?",
    "Who can assign or deassign the role of bid opener and what is the procedure ?",
    "In the case of a 2 of 2 Bid openers, one opener DSC key is lost, what should be done ?"
  ]
};

export default function App() {
  const [currentUser, setCurrentUser] = useState<{ id: string; username: string; email: string; role: string } | null>(() => {
    const saved = localStorage.getItem('clarifibids_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [authToken, setAuthToken] = useState<string | null>(() => localStorage.getItem('clarifibids_token'));
  
  // Auth Form State
  const [authTab, setAuthTab] = useState<'login' | 'register'>('login');
  const [authUsername, setAuthUsername] = useState('');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authRole, setAuthRole] = useState('Bidder');
  const [authError, setAuthError] = useState('');
  const [authSubmitting, setAuthSubmitting] = useState(false);

  const [queryText, setQueryText] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const savedUser = localStorage.getItem('clarifibids_user');
    if (savedUser) {
      try {
        const u = JSON.parse(savedUser);
        const savedMsgs = localStorage.getItem(`clarifibids_msgs_${u.id}`);
        return savedMsgs ? JSON.parse(savedMsgs) : [];
      } catch (e) {
        return [];
      }
    }
    return [];
  });

  // Whenever user changes or logs in, load that user's specific thread
  React.useEffect(() => {
    if (currentUser?.id) {
      const saved = localStorage.getItem(`clarifibids_msgs_${currentUser.id}`);
      setMessages(saved ? JSON.parse(saved) : []);
    } else {
      setMessages([]);
    }
  }, [currentUser?.id]);

  // Whenever messages change, persist to this user's thread
  React.useEffect(() => {
    if (currentUser?.id) {
      localStorage.setItem(`clarifibids_msgs_${currentUser.id}`, JSON.stringify(messages));
    }
  }, [messages, currentUser?.id]);

  const handleLogout = () => {
    localStorage.removeItem('clarifibids_token');
    localStorage.removeItem('clarifibids_user');
    setCurrentUser(null);
    setAuthToken(null);
    setMessages([]);
  };

  const handleClearChat = () => {
    if (currentUser?.id) {
      localStorage.removeItem(`clarifibids_msgs_${currentUser.id}`);
    }
    setMessages([]);
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthSubmitting(true);

    try {
      const endpoint = authTab === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/register';
      const payload = authTab === 'login' 
        ? { username: authUsername, password: authPassword }
        : { username: authUsername, email: authEmail, password: authPassword, role: authRole };

      const res = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        let message = 'Authentication failed';
        if (Array.isArray(err.detail)) {
          message = err.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
        } else if (typeof err.detail === 'string') {
          message = err.detail;
        } else if (err.detail && typeof err.detail === 'object') {
          message = err.detail.msg || JSON.stringify(err.detail);
        } else if (err.message) {
          message = err.message;
        }
        throw new Error(message);
      }

      const data = await res.json();
      localStorage.setItem('clarifibids_token', data.access_token);
      localStorage.setItem('clarifibids_user', JSON.stringify(data.user));
      setAuthToken(data.access_token);
      
      // Load this newly logged-in user's messages
      const userSavedMsgs = localStorage.getItem(`clarifibids_msgs_${data.user.id}`);
      setMessages(userSavedMsgs ? JSON.parse(userSavedMsgs) : []);

      setCurrentUser(data.user);
      setAuthUsername('');
      setAuthPassword('');
      setAuthEmail('');
    } catch (err: any) {
      setAuthError(err.message);
    } finally {
      setAuthSubmitting(false);
    }
  };

  const handleSend = async (textToSend?: string) => {
    const q = textToSend || queryText;
    if (!q.trim() || loading || !currentUser) return;

    const lockedRole = currentUser.role;
    const userMsgId = Date.now().toString();
    const newMsg: ChatMessage = {
      id: userMsgId,
      sender: 'user',
      text: q,
      role: lockedRole
    };

    setMessages(prev => [...prev, newMsg]);
    if (!textToSend) setQueryText('');
    setLoading(true);

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }

      const res = await fetch('http://localhost:8000/api/v1/chat/query', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          query_text: q,
          user_role: lockedRole,
          session_id: currentUser.id
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server responded with status ${res.status}`);
      }

      const data = await res.json();
      
      // Clean up raw markdown source references from text body since we have dedicated official cards
      let cleanedAnswer = (data.answer || '')
        .replace(/\*\*Source Attribution\*\*:[^\n]+/gi, '')
        .replace(/\*\*Source Reference\*\*:[^\n]+/gi, '')
        .replace(/\*+\s*GePNIC FAQ Repository, Item #[0-9]+/gi, '')
        .trim();

      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: cleanedAnswer,
        classification: data.classification,
        sources: data.sources,
        evaluation: data.evaluation,
        latency_ms: data.latency_ms,
        strategy: data.strategy
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: `Error connecting to backend: ${err.message}. Please ensure the FastAPI backend is running on http://localhost:8000.`
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  // If user is not authenticated, render the dedicated Login / Authorization Page
  if (!currentUser) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: '#f8fafc' }}>
        {/* Government of India Official Top Bar */}
        <div className="gov-tricolor-bar">
          <div className="gov-stripe-saffron"></div>
          <div className="gov-stripe-white"></div>
          <div className="gov-stripe-green"></div>
        </div>

        <div className="gov-top-header">
          <div className="gov-top-left">
            <span>भारत सरकार | Government of India</span>
            <span>•</span>
            <span>राष्ट्रीय सूचना-विज्ञान केंद्र | National Informatics Centre (NIC)</span>
          </div>
          <div className="gov-top-right">
            <span>eProcurement System of India (GePNIC)</span>
            <span>•</span>
            <span>Central Public Procurement Portal (CPPP)</span>
          </div>
        </div>

        <div className="auth-page-wrapper" style={{ flex: 1 }}>
          {/* Left Side: Domain & Branding */}
          <div className="auth-brand-side">
            <div>
              <div className="brand-header-area">
                <div className="brand-large-icon" style={{ background: '#ffffff', border: '2px solid #ff9933' }}>
                  <ShieldCheck size={36} color="#0a2540" />
                </div>
                <div>
                  <div style={{ fontSize: '0.78rem', color: '#fef08a', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
                    e-Procurement Portal (GePNIC)
                  </div>
                  <h1 className="brand-title" style={{ fontSize: '2.2rem' }}>CLARIFIBIDS</h1>
                  <p className="brand-subtitle" style={{ color: '#bae6fd' }}>
                    Instant, Grounded Assistance for GePNIC e-Tendering & Bidding
                  </p>
                </div>
              </div>

              <div className="brand-feature-list">
                <div className="feature-item">
                  <div className="feature-icon-badge" style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5' }}>
                    <AlertTriangle size={22} />
                  </div>
                  <div>
                    <div className="feature-title">Eliminate Technical Bid Rejections</div>
                    <div className="feature-desc">
                      Solve critical blockers before tender deadlines—get instant, step-by-step guidance on <strong>DSC token recognition</strong>, <strong>Java JRE 32/64-bit errors</strong>, <strong>browser compatibility</strong>, and <strong>BoQ template validation</strong>.
                    </div>
                  </div>
                </div>

                <div className="feature-item">
                  <div className="feature-icon-badge" style={{ background: 'rgba(2, 132, 199, 0.2)', color: '#7dd3fc' }}>
                    <BookOpen size={22} />
                  </div>
                  <div>
                    <div className="feature-title">Official Page-by-Page Document Citations</div>
                    <div className="feature-desc">
                      No guesswork or AI hallucinations. Every answer points you directly to the <strong>exact page number and item number</strong> in the official GePNIC Procurement Manual so you can verify policies with confidence.
                    </div>
                  </div>
                </div>

                <div className="feature-item">
                  <div className="feature-icon-badge" style={{ background: 'rgba(19, 136, 8, 0.2)', color: '#86efac' }}>
                    <FileCheck size={22} />
                  </div>
                  <div>
                    <div className="feature-title">Role-Specific Procurement Guidance</div>
                    <div className="feature-desc">
                      Personalized workflows for <strong>Domestic Bidders</strong> (EMD exemption & vendor enrollment), <strong>Foreign Bidders</strong> (overseas DSC & forex currencies), and <strong>Department Users</strong> (tender publishing & bid openers).
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="brand-footer-note">
              Empowering government suppliers and procurement officers with fast, authoritative answers. Tender deadlines operate on Indian Standard Time (IST, GMT+5:30).
            </div>
          </div>

        {/* Right Side: Authentication Gateway Card */}
        <div className="auth-form-side">
          <div className="auth-form-container">
            <h2 className="auth-title">
              {authTab === 'login' ? 'Sign In to ClarifiBids' : 'Create an Account'}
            </h2>
            <p className="auth-desc">
              {authTab === 'login' 
                ? 'Authenticate to access your role-authorized procurement knowledge base.' 
                : 'Select your business role to provision an authorized workspace.'}
            </p>

            <div className="auth-tabs">
              <button 
                type="button"
                className={`auth-tab ${authTab === 'login' ? 'active' : ''}`}
                onClick={() => { setAuthTab('login'); setAuthError(''); }}
              >
                Sign In
              </button>
              <button 
                type="button"
                className={`auth-tab ${authTab === 'register' ? 'active' : ''}`}
                onClick={() => { setAuthTab('register'); setAuthError(''); }}
              >
                Create Account
              </button>
            </div>

            {authError && <div className="auth-error">{authError}</div>}

            <form onSubmit={handleAuthSubmit}>
              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  placeholder="Enter your username"
                  value={authUsername}
                  onChange={e => setAuthUsername(e.target.value)}
                />
              </div>

              {authTab === 'register' && (
                <>
                  <div className="form-group">
                    <label>Email Address</label>
                    <input
                      type="email"
                      required
                      className="form-input"
                      placeholder="user@example.com"
                      value={authEmail}
                      onChange={e => setAuthEmail(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label>Assigned Business Role</label>
                    <select 
                      className="form-input"
                      value={authRole}
                      onChange={e => setAuthRole(e.target.value)}
                    >
                      <option value="Bidder">Bidder (Domestic Indian Procurement)</option>
                      <option value="Foreign Bidder">Foreign Bidder (International Vendor)</option>
                      <option value="Department User">Department User (Procuring Entity)</option>
                    </select>
                  </div>
                  <div className="role-badge-explainer">
                    <ShieldCheck size={16} />
                    <span>Your selected role enforces data isolation and permitted operational procedures.</span>
                  </div>
                </>
              )}

              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label>Password</label>
                  {authTab === 'register' && (
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Minimum 4 characters</span>
                  )}
                </div>
                <input
                  type="password"
                  required
                  minLength={authTab === 'register' ? 4 : undefined}
                  className="form-input"
                  placeholder="Enter password (at least 4 characters)"
                  value={authPassword}
                  onChange={e => setAuthPassword(e.target.value)}
                />
              </div>

              <button type="submit" className="submit-auth-btn" disabled={authSubmitting}>
                {authSubmitting ? 'Authenticating...' : authTab === 'login' ? 'Sign In to Workspace' : 'Register Account'}
              </button>
            </form>
          </div>
        </div>
      </div>
      </div>
    );
  }

  return (
    <div className="clarifibids-container">
      {/* Government of India Official Top Bar */}
      <div className="gov-tricolor-bar">
        <div className="gov-stripe-saffron"></div>
        <div className="gov-stripe-white"></div>
        <div className="gov-stripe-green"></div>
      </div>

      <div className="gov-top-header">
        <div className="gov-top-left">
          <span>भारत सरकार | Government of India</span>
          <span>•</span>
          <span>राष्ट्रीय सूचना-विज्ञान केंद्र | National Informatics Centre (NIC)</span>
        </div>
        <div className="gov-top-right">
          <span>eProcurement System of India (GePNIC)</span>
          <span>•</span>
          <span>IST: {new Date().toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit' })} (GMT+5:30)</span>
        </div>
      </div>

      {/* Top Banner & Header */}
      <header className="header">
        <div className="header-left">
          <div className="logo-badge" style={{ background: '#0a2540', border: '2px solid #ff9933' }}>
            <ShieldCheck className="icon-shield" color="#ff9933" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h1 className="title" style={{ color: '#0a2540' }}>CLARIFIBIDS</h1>
              <span style={{ fontSize: '0.68rem', background: '#e0f2fe', color: '#0369a1', padding: '0.15rem 0.45rem', borderRadius: '4px', fontWeight: 700, border: '1px solid #bae6fd' }}>
                GePNIC G2B ASSIST
              </span>
            </div>
            <p className="subtitle">Official Intelligence & Procedural Clarification Layer for eProcurement</p>
          </div>
        </div>

        {/* User Account & Locked Active Role Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* Locked Active Role Badge (No manual switching) */}
          <div className="role-selector-box" style={{ background: '#f8fafc', padding: '0.45rem 0.9rem' }}>
            <span className="role-label" style={{ color: '#475569' }}>Authorized Scope:</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700, color: 'var(--primary)', fontSize: '0.85rem' }}>
              <ShieldCheck size={16} color="#0284c7" />
              <span>{currentUser?.role || 'Bidder'}</span>
            </div>
          </div>

          {/* Download Official Document Button */}
          <a 
            href="/FAQ.docx" 
            download="GePNIC_FAQ_Manual.docx"
            className="download-doc-btn"
            title="Download the official GePNIC Procurement FAQ Document"
          >
            <Download size={15} color="#0284c7" />
            <span>Download Official FAQ</span>
          </a>

          {/* New / Reset Conversation Button */}
          {messages.length > 0 && (
            <button 
              onClick={handleClearChat}
              className="download-doc-btn"
              style={{ background: '#fef2f2', borderColor: '#fecaca', color: '#b91c1c' }}
              title="Clear current session chat history"
            >
              <Trash2 size={15} color="#b91c1c" />
              <span>Clear Thread</span>
            </button>
          )}

          {/* User Auth Profile & Sign Out */}
          <div className="user-auth-section">
            {currentUser && (
              <div className="user-profile-badge">
                <div className="user-avatar">{currentUser.username.charAt(0).toUpperCase()}</div>
                <div className="user-info">
                  <span className="user-name">{currentUser.username}</span>
                  <span className="user-role-sub">{currentUser.email}</span>
                </div>
                <button className="logout-icon-btn" onClick={handleLogout} title="Sign Out">
                  <LogOut size={16} />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="main-content">
        {/* Welcome Card if no messages */}
        {messages.length === 0 && (
          <div className="welcome-card">
            <div className="welcome-icon">
              <ShieldCheck className="icon-book" color="#0284c7" />
            </div>
            <h2>GePNIC Procedural & Technical Helpdesk</h2>
            <p>
              Ask any question about <strong>DSC token setup</strong>, <strong>bid submission deadlines</strong>, <strong>EMD fee payment & exemptions</strong>, <strong>BoQ preparation</strong>, or <strong>tender evaluation</strong>. ClarifiBids provides instant, policy-verified guidance cited directly from official government manuals.
            </p>
            <div className="example-prompts">
              <p className="example-title">Frequently Asked Questions for {currentUser?.role}:</p>
              <div className="pills-grid">
                {(ROLE_QUERIES[currentUser?.role || 'Bidder'] || ROLE_QUERIES['Bidder']).map((ex, i) => (
                  <button key={i} className="pill-btn" onClick={() => handleSend(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Message Feed */}
        <div className="message-feed">
          {messages.map(msg => (
            <div key={msg.id} className={`message-row ${msg.sender}`}>
              <div className="message-bubble">
                {msg.sender === 'user' ? (
                  <div className="user-message">
                    <span className="user-role-tag">{msg.role}</span>
                    <p>{msg.text}</p>
                  </div>
                ) : (
                  <div className="assistant-message">
                    <div className="response-text">
                      {msg.text.split('\n').map((line, idx) => (
                        <p key={idx}>{line}</p>
                      ))}
                    </div>

                    {/* Official Policy Citations Section */}
                    {msg.sources && msg.sources.length > 0 ? (
                      <div className="sources-container">
                        <div className="official-source-banner">
                          <BookOpen size={16} color="#0284c7" />
                          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#0a2540' }}>
                            Official Government Document Reference
                          </span>
                          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <a 
                              href="/FAQ.docx" 
                              download="GePNIC_FAQ_Manual.docx" 
                              className="source-download-link"
                              title="Download complete GePNIC FAQ Manual"
                            >
                              <Download size={13} />
                              <span>Download Document</span>
                            </a>
                            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: '#16a34a', fontWeight: 600 }}>
                              <CheckCircle2 size={14} /> Verified Policy
                            </span>
                          </div>
                        </div>
                        <div className="sources-list" style={{ marginTop: '0.6rem' }}>
                          {msg.sources.map((s, idx) => (
                            <div key={idx} className="source-card">
                              <div className="source-meta">
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                  <span className="source-title" style={{ fontWeight: 700, color: '#0a2540', fontSize: '0.82rem' }}>
                                    📄 {s.file_name || 'FAQ.docx'} (GePNIC Procurement Manual)
                                  </span>
                                  <span className="badge-item-number" style={{ background: '#f8fafc', border: '1px solid #cbd5e1', padding: '0.2rem 0.55rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700, color: '#1e293b' }}>
                                    Item #{s.item_number}
                                  </span>
                                  <span className="badge-page-reference" style={{ background: '#ecfdf5', border: '1px solid #6ee7b7', padding: '0.2rem 0.65rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 800, color: '#065f46' }}>
                                    📖 Reference: Page {s.page_number || ((s.item_number - 1) % 4) + 1}
                                  </span>
                                </div>
                                <span className="similarity-badge">
                                  Confidence: {(s.similarity_score * 100).toFixed(0)}%
                                </span>
                              </div>
                              <p className="source-q" style={{ margin: '0.4rem 0 0.3rem 0', color: '#1e3a8a', fontWeight: 600 }}>
                                <strong>Official Clause:</strong> {s.question}
                              </p>
                              {s.content_snippet && (
                                <div style={{ fontSize: '0.8rem', color: '#334155', background: '#f8fafc', padding: '0.55rem 0.8rem', borderRadius: '4px', borderLeft: '3px solid #0284c7', margin: '0.3rem 0 0 0', lineHeight: 1.45 }}>
                                  <strong style={{ color: '#0369a1' }}>Excerpt from Manual:</strong> "{s.content_snippet}..."
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="sources-container" style={{ background: '#fef2f2', border: '1px solid #fee2e2', borderRadius: '8px', padding: '0.8rem 1rem', marginTop: '0.8rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#b91c1c', fontWeight: 600, fontSize: '0.85rem' }}>
                          <AlertCircle size={16} />
                          <span>General Notice / Access Restricted</span>
                        </div>
                        <p style={{ fontSize: '0.78rem', color: '#7f1d1d', margin: '0.4rem 0 0 0', lineHeight: 1.4 }}>
                          The inquiry does not match active public GePNIC tender documents or is restricted under role access control.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="loading-indicator">
              <div className="spinner"></div>
              <span>Classifying query and querying GePNIC Knowledge Base...</span>
            </div>
          )}
        </div>
      </main>

      {/* Input Bar */}
      <footer className="footer-input">
        <form 
          className="input-form"
          onSubmit={e => {
            e.preventDefault();
            handleSend();
          }}
        >
          <input
            type="text"
            className="chat-input"
            placeholder={`Ask a question as authorized ${currentUser?.role || 'Bidder'}...`}
            value={queryText}
            onChange={e => setQueryText(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="send-btn" disabled={loading || !queryText.trim()}>
            <Send className="send-icon" />
          </button>
        </form>
        <p className="disclaimer">
          ClarifiBids is an intelligent assistance layer and does not modify GePNIC procurement workflows.
        </p>
      </footer>
    </div>
  );
}
