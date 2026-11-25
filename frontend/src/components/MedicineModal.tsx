import { useState } from 'react';
import { motion } from 'framer-motion';
import { Pill, Search } from 'lucide-react';
import Modal from './Modal';
import { ApiError, postJSON } from '../api';
import type { MedicineInfo } from '../types';

const POPULAR = ['Paracetamol', 'Dolo 650', 'Amoxicillin', 'Cetirizine', 'Ibuprofen', 'Azithromycin'];

export default function MedicineModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MedicineInfo | null>(null);
  const [recent, setRecent] = useState<string[]>([]);

  const lookup = async (name?: string) => {
    const term = (name ?? query).trim();
    if (!term) return;
    setQuery(term);
    setLoading(true);
    setResult(null);
    try {
      const json = await postJSON<MedicineInfo>('/api/v1/lookups/medicine', { name: term });
      setResult(json);
      if (!json.error) {
        setRecent((prev) => [term, ...prev.filter((s) => s.toLowerCase() !== term.toLowerCase())].slice(0, 5));
      }
    } catch (err) {
      const msg = err instanceof ApiError && err.status !== 0 ? err.message : 'Could not connect to Health-U. Please check your connection and try again.';
      setResult({ error: msg });
    } finally {
      setLoading(false);
    }
  };

  const close = () => {
    setResult(null);
    setQuery('');
    onClose();
  };

  return (
    <Modal open={open} title="Know your medicine" onClose={close}>
      <div className="search-row">
        <Search size={18} color="var(--muted)" />
        <input
          placeholder="Search a medicine, e.g. Metformin"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && lookup()}
          autoFocus
        />
        <button className="btn btn-primary" onClick={() => lookup()} disabled={loading || !query.trim()}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>

      {!result && !loading && (
        <>
          <div className="pill-row">
            {POPULAR.map((m) => (
              <button key={m} className="pill" onClick={() => lookup(m)}>{m}</button>
            ))}
          </div>
          {recent.length > 0 && (
            <div className="pill-row">
              <span style={{ color: 'var(--muted)', fontSize: '0.85rem', alignSelf: 'center' }}>Recent:</span>
              {recent.map((m) => (
                <button key={m} className="pill" onClick={() => lookup(m)}>{m}</button>
              ))}
            </div>
          )}
          <div className="warn-line" style={{ marginTop: 22 }}>
            Always confirm medicine use with a doctor or pharmacist before taking anything.
          </div>
        </>
      )}

      {loading && (
        <div className="empty-hint">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1.2, ease: 'linear' }}
            style={{ width: 34, height: 34, borderRadius: '50%', border: '3px solid var(--brand-100)', borderTopColor: 'var(--brand-700)', margin: '0 auto 12px' }}
          />
          Looking up {query}…
        </div>
      )}

      {result?.error && (
        <div className="empty-hint">
          <Pill size={34} color="var(--high)" />
          <p style={{ color: 'var(--high)', fontWeight: 600, margin: '10px 0 14px' }}>{result.error}</p>
          <button className="btn btn-ghost" onClick={() => setResult(null)}>Try again</button>
        </div>
      )}

      {result && !result.error && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <div className="med-head">
            <div style={{ width: 52, height: 52, borderRadius: 16, background: 'var(--brand-100)', display: 'grid', placeItems: 'center', color: 'var(--brand-700)' }}>
              <Pill size={24} />
            </div>
            <div>
              <h2>{result.medicine}</h2>
              <small>{result.subtitle}</small>
            </div>
          </div>
          {result.tags && result.tags.length > 0 && (
            <div className="pill-row">
              {result.tags.map((t) => <span key={t} className="tag">{t}</span>)}
            </div>
          )}
          {result.description && <p style={{ marginTop: 14, color: 'var(--ink-2)' }}>{result.description}</p>}

          <div className="list-grid">
            <ListBox title="Uses" items={result.uses} />
            <ListBox title="Side effects" items={result.side_effects} />
            <ListBox title="Precautions" items={result.precautions} />
            <ListBox title="Warnings" items={result.warnings} warn />
          </div>

          {result.related_medicines && result.related_medicines.length > 0 && (
            <>
              <p style={{ marginTop: 18, fontWeight: 700, fontSize: '0.9rem' }}>Related medicines</p>
              <div className="pill-row">
                {result.related_medicines.map((m) => (
                  <button key={m} className="pill" onClick={() => lookup(m)}>{m}</button>
                ))}
              </div>
            </>
          )}
        </motion.div>
      )}
    </Modal>
  );
}

function ListBox({ title, items, warn }: { title: string; items?: string[]; warn?: boolean }) {
  return (
    <div className={`list-box ${warn ? 'warn' : ''}`}>
      <h4>{title}</h4>
      {items && items.length > 0 ? (
        <ul>{items.map((i) => <li key={i}>{i}</li>)}</ul>
      ) : (
        <p style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>No information available.</p>
      )}
    </div>
  );
}
