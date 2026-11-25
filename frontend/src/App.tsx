import { useEffect, useState } from 'react';
import { ApiError, SESSION_EXPIRED_EVENT, getJSON, getToken, setToken } from './api';
import { AnimatePresence, motion } from 'framer-motion';
import Navbar from './components/Navbar';
import Splash from './components/Splash';
import Landing from './components/Landing';
import Auth from './components/Auth';
import ChatShell from './components/ChatShell';
import type { AuthUser, View } from './types';

export default function App() {
  const [showSplash, setShowSplash] = useState(true);
  const [view, setView] = useState<View>('portfolio');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setShowSplash(false), 2600);
    return () => clearTimeout(t);
  }, []);

  // Restore a saved session. A stored token is only trusted after the server confirms it.
  useEffect(() => {
    const checked = getToken();
    if (checked) {
      getJSON<AuthUser>('/api/v1/auth/me')
        .then((u) => {
          // Ignore the answer if the user has signed in again in the meantime.
          if (getToken() !== checked) return;
          setUser(u);
          setView('app');
        })
        .catch((err) => {
          if (getToken() === checked && err instanceof ApiError && err.status === 401) setToken(null);
        });
    }
    const expired = (e: Event) => {
      const reason = (e as CustomEvent<string>).detail;
      setUser(null);
      setView('login');
      setNotice(
        'Your session ended. Please sign in again. Your chat history is still saved in this browser.' +
          (reason ? ` (Reason: ${reason})` : ''),
      );
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
  }, []);

  const goHome = () => setView(user ? 'app' : 'portfolio');
  const logout = () => {
    setToken(null);
    setUser(null);
    setView('portfolio');
  };
  const onAuthed = (u: AuthUser) => {
    setNotice(null);
    setUser(u);
    setView('app');
  };
  const scrollToFeatures = () => {
    if (view !== 'portfolio') setView('portfolio');
    setTimeout(() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' }), 60);
  };

  const inApp = !!user && view === 'app';

  return (
    <>
      <AnimatePresence>{showSplash && <Splash key="splash" />}</AnimatePresence>

      {inApp ? (
        <ChatShell user={user} onLogout={logout} />
      ) : (
        <div className="app-root">
          <Navbar
            user={user}
            onHome={goHome}
            onLogin={() => setView('login')}
            onRegister={() => setView('register')}
            onLogout={logout}
            onFeatures={scrollToFeatures}
          />
          {notice && view !== 'app' && (
            <div role="alert" style={{ maxWidth: 680, margin: '1rem auto 0', padding: '0.7rem 1rem', borderRadius: 10, background: '#fff4e5', color: '#7a4a00', border: '1px solid #f3c88a', fontSize: '0.92rem' }}>
              {notice}
            </div>
          )}
          <main>
            <AnimatePresence mode="wait">
              <motion.div
                key={view}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3 }}
              >
                {view === 'portfolio' && (
                  <Landing onStart={() => setView('register')} onLogin={() => setView('login')} />
                )}
                {(view === 'login' || view === 'register') && (
                  <Auth
                    mode={view}
                    onSuccess={onAuthed}
                    onSwitch={(m) => setView(m)}
                  />
                )}
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      )}
    </>
  );
}
