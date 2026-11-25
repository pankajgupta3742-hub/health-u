import { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import { ApiError, postJSON, setToken } from '../api';
import type { AuthUser } from '../types';

interface Props {
  mode: 'login' | 'register';
  onSuccess: (user: AuthUser) => void;
  onSwitch: (mode: 'login' | 'register') => void;
}

export default function Auth({ mode, onSuccess, onSwitch }: Props) {
  const [form, setForm] = useState({ email: '', password: '', name: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const isLogin = mode === 'login';

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!form.email || !form.password) {
      setError('Please enter your email and password.');
      return;
    }
    setLoading(true);
    try {
      const json = await postJSON<{ access_token: string; user: AuthUser }>(
        isLogin ? '/api/v1/auth/login' : '/api/v1/auth/register',
        isLogin
          ? { email: form.email, password: form.password }
          : { email: form.email, password: form.password, name: form.name },
      );
      setToken(json.access_token);
      onSuccess(json.user);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Could not reach the server. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrap container">
      <motion.div
        className="auth-card"
        style={{ margin: '0 auto' }}
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <h2>{isLogin ? 'Welcome back' : 'Create your account'}</h2>
        <p>{isLogin ? 'Log in to continue to your health assistant.' : 'Takes less than a minute.'}</p>

        <form onSubmit={submit}>
          {!isLogin && (
            <div className="field">
              <label htmlFor="name">Full name</label>
              <input
                id="name"
                className="input"
                placeholder="Jane Doe"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
          )}
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              className="input"
              placeholder="name@example.com"
              autoComplete="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              className="input"
              placeholder="••••••••"
              autoComplete={isLogin ? 'current-password' : 'new-password'}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>

          {error && <div className="error-text" role="alert">{error}</div>}

          <motion.button
            type="submit"
            className="btn btn-primary btn-block btn-lg"
            disabled={loading}
            whileHover={{ scale: loading ? 1 : 1.01 }}
            whileTap={{ scale: loading ? 1 : 0.98 }}
          >
            {loading ? 'Please wait…' : isLogin ? 'Log in' : 'Create account'} <ArrowRight size={18} />
          </motion.button>
        </form>

        <p className="auth-switch">
          {isLogin ? "Don't have an account? " : 'Already have an account? '}
          <button onClick={() => onSwitch(isLogin ? 'register' : 'login')}>
            {isLogin ? 'Sign up' : 'Log in'}
          </button>
        </p>
      </motion.div>
    </div>
  );
}
