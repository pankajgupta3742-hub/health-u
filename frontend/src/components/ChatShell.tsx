import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  BookOpen,
  HeartPulse,
  LogOut,
  MessageSquare,
  Pill,
  Plus,
  Search,
  Send,
  Trash2,
  ExternalLink,
  FileText,
  FlaskConical,
} from 'lucide-react';
import { postJSON } from '../api';
import { formatMessage } from '../utils/format';
import Triage from './Triage';
import MedicineModal from './MedicineModal';
import DictionaryModal from './DictionaryModal';
import ExternalTriageModal from './ExternalTriageModal';
import RecordsModal from './RecordsModal';
import DiseaseModelsModal from './DiseaseModelsModal';
import type { AuthUser, Chat, ChatMessage } from '../types';

const START_TRIAGE = 'Start Symptom Analysis';

const QUICK_ACTIONS = [
  { label: 'Symptom check', icon: <HeartPulse size={15} />, id: 'triage' },
  { label: 'Know your medicine', icon: <Pill size={15} />, id: 'medicine' },
  { label: 'Medical dictionary', icon: <BookOpen size={15} />, id: 'dictionary' },
  { label: 'Ask a health question', icon: <MessageSquare size={15} />, id: 'ask' },
  { label: 'Disease models', icon: <FlaskConical size={15} />, id: 'models' },
  { label: 'My records', icon: <FileText size={15} />, id: 'records' },
] as const;

// Chat history is stored per account, so two people sharing a browser never see each other's chats.
function historyKey(email: string): string {
  return `healthu_history:${email.toLowerCase()}`;
}

function loadHistory(email: string): Chat[] {
  try {
    const raw = localStorage.getItem(historyKey(email));
    return raw ? (JSON.parse(raw) as Chat[]) : [];
  } catch {
    return [];
  }
}

export default function ChatShell({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [history, setHistory] = useState<Chat[]>(() => loadHistory(user.email));
  const [search, setSearch] = useState('');
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const [mode, setMode] = useState<'chat' | 'triage'>('chat');
  const [modal, setModal] = useState<'medicine' | 'dictionary' | 'external' | 'records' | 'models' | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const [triageKey, setTriageKey] = useState(0);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, typing, mode]);

  const persist = (next: Chat[]) => {
    setHistory(next);
    try {
      localStorage.setItem(historyKey(user.email), JSON.stringify(next));
    } catch {
      /* storage full or unavailable: keep in memory only */
    }
  };

  const saveConversation = (msgs: ChatMessage[], chatId: string | null) => {
    if (chatId) {
      persist(history.map((c) => (c.id === chatId ? { ...c, messages: msgs, timestamp: Date.now() } : c)));
      return chatId;
    }
    const id = Date.now().toString();
    const first = msgs[0]?.content ?? 'New chat';
    const newChat: Chat = {
      id,
      title: first.length > 32 ? first.slice(0, 32) + '…' : first,
      messages: msgs,
      timestamp: Date.now(),
    };
    persist([newChat, ...history]);
    setCurrentChatId(id);
    return id;
  };

  const send = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || typing) return;

    if (msg === START_TRIAGE) {
      setMode('triage');
      setTriageKey((k) => k + 1);
      return;
    }

    const next: ChatMessage[] = [...messages, { role: 'user', content: msg }];
    setMessages(next);
    setInput('');
    setTyping(true);

    let aiMsg: ChatMessage;
    try {
      const json = await postJSON<{ reply: string; suggestions?: string[] }>('/api/v1/chat', {
        message: msg,
        history: next.map((m) => ({ role: m.role, content: m.content })),
      });
      aiMsg = {
        role: 'ai',
        content: json.reply,
        isNew: true,
        suggestions: [START_TRIAGE, ...(json.suggestions ?? []).filter((s) => s !== START_TRIAGE)],
      };
    } catch {
      aiMsg = { role: 'ai', content: 'Sorry, I could not reach the server. Please try again.', isNew: true, suggestions: [] };
    }
    const finalMsgs = [...next, aiMsg];
    setMessages(finalMsgs);
    setTyping(false);
    saveConversation(finalMsgs, currentChatId);
  };

  const handleSuggestion = (s: string) => {
    if (s === START_TRIAGE) return setMode('triage');
    if (s.includes('Medicine')) return setModal('medicine');
    if (s.includes('Dictionary')) return setModal('dictionary');
    send(s);
  };

  const newChat = () => {
    setMessages([]);
    setCurrentChatId(null);
    setMode('chat');
    setInput('');
  };

  const openChat = (c: Chat) => {
    setCurrentChatId(c.id);
    // Saved replies should appear instantly, not re-type.
    setMessages(c.messages.map((m) => ({ ...m, isNew: false })));
    setMode('chat');
  };

  const deleteChat = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    persist(history.filter((c) => c.id !== id));
    if (currentChatId === id) newChat();
  };

  const runQuick = (id: (typeof QUICK_ACTIONS)[number]['id']) => {
    if (id === 'triage') setMode('triage');
    else if (id === 'medicine') setModal('medicine');
    else if (id === 'dictionary') setModal('dictionary');
    else if (id === 'records') setModal('records');
    else if (id === 'models') setModal('models');
    else {
      setMode('chat');
      document.getElementById('composer')?.focus();
    }
  };

  const filtered = history.filter((c) => (c.title || 'New chat').toLowerCase().includes(search.toLowerCase()));
  const initial = user.email[0]?.toUpperCase() ?? 'U';
  const empty = messages.length === 0 && mode === 'chat';

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-head">
          <button className="brand" onClick={newChat} style={{ fontSize: '1rem' }}>
            <span className="brand-mark" style={{ width: 30, height: 30 }}><Activity size={16} strokeWidth={2.6} /></span>
            Health-U
          </button>
          <motion.button className="chip" onClick={newChat} whileTap={{ scale: 0.95 }} style={{ padding: '0.4rem 0.7rem' }} aria-label="New chat">
            <Plus size={15} /> New
          </motion.button>
        </div>

        <div className="sidebar-search">
          <div className="search-row" style={{ padding: '4px 10px 4px 12px', borderRadius: 12 }}>
            <Search size={15} color="var(--muted)" />
            <input
              placeholder="Search chats"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ fontSize: '0.9rem' }}
            />
          </div>
        </div>

        <div className="sidebar-section">Recent</div>
        <div className="sidebar-list">
          {filtered.length === 0 ? (
            <div style={{ padding: '8px 12px', color: 'var(--muted)', fontSize: '0.88rem' }}>
              {search ? 'No matching chats' : 'No conversations yet'}
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {filtered.map((c) => (
                <motion.div
                  key={c.id}
                  layout
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  className={`chat-item ${currentChatId === c.id ? 'active' : ''}`}
                  onClick={() => openChat(c)}
                >
                  <MessageSquare size={14} />
                  <span>{c.title || 'New chat'}</span>
                  <button className="del" onClick={(e) => deleteChat(e, c.id)} aria-label="Delete chat">
                    <Trash2 size={13} />
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          )}
        </div>

        <div className="sidebar-foot">
          <div className="avatar sm">{initial}</div>
          <div className="sidebar-user">
            <div>{user.email}</div>
            <small>Signed in</small>
          </div>
          <button className="del" onClick={onLogout} aria-label="Log out" title="Log out" style={{ background: 'none', border: 0, color: 'var(--muted)' }}>
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <section className="main">
        <header className="main-top">
          <h3>{mode === 'triage' ? 'Symptom check' : 'Health assistant'}</h3>
          <button className="btn btn-ghost" style={{ padding: '0.45rem 0.9rem', fontSize: '0.85rem' }} onClick={() => setModal('external')}>
            <ExternalLink size={14} /> External tool
          </button>
        </header>

        <div className="main-body">
          {mode === 'triage' ? (
            <Triage key={triageKey} onExit={() => setMode('chat')} />
          ) : empty ? (
            <motion.div className="empty-chat" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
              <div className="brand-mark" style={{ width: 52, height: 52, borderRadius: 16 }}>
                <Activity size={26} strokeWidth={2.4} />
              </div>
              <h1>How can I help you today?</h1>
              <div className="composer" style={{ width: 'min(680px, 100%)' }}>
                <textarea
                  id="composer"
                  rows={1}
                  placeholder="Describe a symptom or ask a health question"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <button className="send" onClick={() => send()} disabled={!input.trim() || typing} aria-label="Send">
                  <Send size={17} />
                </button>
              </div>
              <div className="chips">
                {QUICK_ACTIONS.map((q, i) => (
                  <motion.button
                    key={q.id}
                    className="chip"
                    onClick={() => runQuick(q.id)}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + i * 0.07 }}
                    whileHover={{ y: -2 }}
                  >
                    {q.icon} {q.label}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          ) : (
            <div className="messages">
              {messages.map((m, i) => (
                <motion.div
                  key={i}
                  className={`msg ${m.role}`}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  {m.role === 'ai' ? (
                    <div className="ai-mark"><Activity size={15} strokeWidth={2.6} /></div>
                  ) : (
                    <div className="avatar sm">{initial}</div>
                  )}
                  <div className="msg-bubble">
                    <div className="msg-sender">{m.role === 'ai' ? 'Health-U' : 'You'}</div>
                    <div className="formatted">
                      {m.role === 'ai' && m.isNew ? <Typewriter text={m.content} /> : formatMessage(m.content)}
                    </div>
                    {m.role === 'ai' && m.suggestions && m.suggestions.length > 0 && (
                      <div className="suggestions">
                        {m.suggestions.map((s) => (
                          <button key={s} className="suggestion" onClick={() => handleSuggestion(s)}>{s}</button>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}
              {typing && (
                <div className="msg ai">
                  <div className="ai-mark"><Activity size={15} strokeWidth={2.6} /></div>
                  <div className="msg-bubble">
                    <div className="thinking">
                      <motion.i animate={{ opacity: [0.2, 1, 0.2] }} transition={{ repeat: Infinity, duration: 1 }} />
                      <motion.i animate={{ opacity: [0.2, 1, 0.2] }} transition={{ repeat: Infinity, duration: 1, delay: 0.2 }} />
                      <motion.i animate={{ opacity: [0.2, 1, 0.2] }} transition={{ repeat: Infinity, duration: 1, delay: 0.4 }} />
                      <span style={{ marginLeft: 6 }}>Thinking</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}
        </div>

        {mode === 'chat' && !empty && (
          <div className="chat-input-area">
            <div className="composer" style={{ width: 'min(780px, 100%)' }}>
              <textarea
                id="composer"
                rows={1}
                placeholder="Ask a follow-up question"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
              />
              <button className="send" onClick={() => send()} disabled={!input.trim() || typing} aria-label="Send">
                <Send size={17} />
              </button>
            </div>
            <div className="chat-foot-note">
              Health-U gives educational information only. In an emergency, call your local emergency number.
            </div>
          </div>
        )}
      </section>

      <MedicineModal open={modal === 'medicine'} onClose={() => setModal(null)} />
      <DictionaryModal open={modal === 'dictionary'} onClose={() => setModal(null)} />
      <ExternalTriageModal open={modal === 'external'} onClose={() => setModal(null)} />
      <RecordsModal open={modal === 'records'} onClose={() => setModal(null)} />
      <DiseaseModelsModal open={modal === 'models'} onClose={() => setModal(null)} />
    </div>
  );
}

// Types the AI reply out gradually. Reveals a few characters per tick.
function Typewriter({ text }: { text: string }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    setShown(0);
    const id = setInterval(() => {
      setShown((n) => {
        const next = Math.min(text.length, n + 3);
        if (next >= text.length) clearInterval(id);
        return next;
      });
    }, 12);
    return () => clearInterval(id);
  }, [text]);
  return <>{formatMessage(text.slice(0, shown))}</>;
}
