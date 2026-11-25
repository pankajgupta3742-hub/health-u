import { Activity } from 'lucide-react';
import { motion } from 'framer-motion';

interface Props {
  user: { email: string } | null;
  onHome: () => void;
  onLogin: () => void;
  onRegister: () => void;
  onLogout: () => void;
  onFeatures: () => void;
}

export default function Navbar({ user, onHome, onLogin, onRegister, onLogout, onFeatures }: Props) {
  return (
    <motion.nav
      className="navbar"
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <div className="container navbar-inner">
        <button className="brand" onClick={onHome} aria-label="Health-U home">
          <span className="brand-mark">
            <Activity size={18} strokeWidth={2.6} />
          </span>
          <span>Health-U</span>
        </button>

        <div className="nav-links">
          {user ? (
            <>
              <button className="nav-link" onClick={onHome}>Assistant</button>
              <button className="btn btn-ghost" onClick={onLogout} style={{ padding: '0.5rem 1rem' }}>
                Log out
              </button>
            </>
          ) : (
            <>
              <button className="nav-link" onClick={onFeatures}>Features</button>
              <button className="nav-link" onClick={onLogin}>Log in</button>
              <motion.button
                className="btn btn-primary"
                onClick={onRegister}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                style={{ padding: '0.6rem 1.1rem' }}
              >
                Get started
              </motion.button>
            </>
          )}
        </div>
      </div>
    </motion.nav>
  );
}
