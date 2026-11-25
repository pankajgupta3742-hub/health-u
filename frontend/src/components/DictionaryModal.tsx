import { useState } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Search } from 'lucide-react';
import Modal from './Modal';
import { postJSON, ApiError } from '../api';
import type { DictionaryInfo } from '../types';

export default function DictionaryModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [term, setTerm] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DictionaryInfo | null>(null);

  const lookup = async (t?: string) => {
    const search = (t ?? term).trim();
    if (!search) return;
    setTerm(search);
    setLoading(true);
    setResult(null);
    try {
      const json = await postJSON<DictionaryInfo>('/api/v1/lookups/dictionary', { term: search });
      setResult(json);
    } catch (err) {
      const msg = err instanceof ApiError && err.status !== 0 ? err.message : 'Could not connect to Health-U. Please check your connection and try again.';
      setResult({ error: msg });
    } finally {
      setLoading(false);
    }
  };

  const close = () => {
    setResult(null);
    setTerm('');
    onClose();
  };

  return (
    <Modal open={open} title="Medical dictionary" onClose={close}>
      <div className="search-row">
        <Search size={18} color="var(--muted)" />
        <input
          placeholder="Search a medical term, e.g. Tachycardia"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && lookup()}
          autoFocus
        />
        <button className="btn btn-primary" onClick={() => lookup()} disabled={loading || !term.trim()}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>

      {!result && !loading && (
        <div className="empty-hint">
          <BookOpen size={34} color="var(--brand-500)" />
          <p style={{ margin: '10px 0 0' }}>Search for a disease, symptom, test or other medical term.</p>
        </div>
      )}

      {loading && (
        <div className="empty-hint">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1.2, ease: 'linear' }}
            style={{ width: 34, height: 34, borderRadius: '50%', border: '3px solid var(--brand-100)', borderTopColor: 'var(--brand-700)', margin: '0 auto 12px' }}
          />
          Looking up {term}…
        </div>
      )}

      {result?.error && (
        <div className="empty-hint">
          <p style={{ color: 'var(--high)', fontWeight: 600 }}>{result.error}</p>
          <button className="btn btn-ghost" style={{ marginTop: 12 }} onClick={() => setResult(null)}>Try again</button>
        </div>
      )}

      {result && !result.error && (
        <motion.div className="def-card" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <div>
            <div className="term">{result.term}</div>
            {result.phonetic && <div className="phon">{result.phonetic}</div>}
          </div>
          {result.simple_definition && (
            <div className="block"><h4>Simple definition</h4><p>{result.simple_definition}</p></div>
          )}
          {result.clinical_definition && (
            <div className="block"><h4>Clinical definition</h4><p>{result.clinical_definition}</p></div>
          )}
          {result.context && (
            <div className="block"><h4>Usage and context</h4><p>{result.context}</p></div>
          )}
          {result.related_terms && result.related_terms.length > 0 && (
            <div>
              <p style={{ fontWeight: 700, fontSize: '0.9rem', marginBottom: 8 }}>Related terms</p>
              <div className="pill-row" style={{ marginTop: 0 }}>
                {result.related_terms.map((t) => (
                  <button key={t} className="pill" onClick={() => lookup(t)}>{t}</button>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </Modal>
  );
}
