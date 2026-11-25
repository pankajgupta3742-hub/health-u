import { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import Modal from './Modal';
import { API_URL, ApiError, getJSON, getToken, postJSON } from '../api';
import type { FeatureSpec, MissingDataView, ModelCatalogItem, ModelDetail, PredictionResult, ProvenanceRow } from '../types';
import MissingDataReview, { type Decision } from './MissingDataReview';

const humanize = (v: string) => v.replace(/_/g, ' ');

function errorOf(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

// Form state keeps raw strings so a half-typed number does not vanish while the user types.
type Values = Record<string, string>;

function initialValues(features: FeatureSpec[]): Values {
  const out: Values = {};
  for (const f of features) {
    // Blank on purpose: a blank field means "use the training default", and the result lists those fields.
    out[f.name] = '';
  }
  return out;
}

export default function DiseaseModelsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [catalog, setCatalog] = useState<ModelCatalogItem[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ModelDetail | null>(null);
  const [values, setValues] = useState<Values>({});
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [view, setView] = useState<MissingDataView | null>(null);
  const [correcting, setCorrecting] = useState<{ field: string; value: string } | null>(null);
  const [staleNote, setStaleNote] = useState(false);
  const [card, setCard] = useState<string | null>(null);
  const [showCard, setShowCard] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (result) resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [result]);

  useEffect(() => {
    if (!open) return;
    setError('');
    setResult(null);
    setView(null);
    setCard(null);
    setShowCard(false);
    getJSON<{ models: ModelCatalogItem[] }>('/api/v1/models')
      .then((r) => setCatalog(r.models))
      .catch((err) => setError(errorOf(err, 'Could not load the disease models.')));
  }, [open]);

  useEffect(() => {
    if (!selected) return;
    setDetail(null);
    setResult(null);
    setView(null);
    setCard(null);
    setShowCard(false);
    setError('');
    getJSON<ModelDetail>(`/api/v1/models/${selected}`)
      .then((d) => {
        setDetail(d);
        setValues(initialValues(d.features));
      })
      .catch((err) => setError(errorOf(err, 'Could not load this model.')));
  }, [selected]);

  // Step 1: the patient's own answers go to the server, which lists what is missing and what can be proposed.
  // Nothing is filled in here. Every suggestion has to be accepted, edited or answered by the patient.
  const checkInfo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detail) return;
    const payload: Record<string, number | string> = {};
    for (const f of detail.features) {
      const raw = (values[f.name] ?? '').trim();
      if (raw === '') continue;
      payload[f.name] = f.type === 'categorical' ? raw : Number(raw);
    }
    setBusy(true);
    setError('');
    setResult(null);
    try {
      setView(await postJSON<MissingDataView>('/api/v1/missing-data/reports', { model: detail.key, features: payload }));
    } catch (err) {
      setError(errorOf(err, 'Could not check your information.'));
    } finally {
      setBusy(false);
    }
  };

  // Step 2: the patient's choice for one or more fields (accept, reject, edit, answer, or unknown).
  const decide = async (decisions: Decision[]) => {
    if (!view) return;
    setBusy(true);
    setError('');
    try {
      setView(await postJSON<MissingDataView>(`/api/v1/missing-data/reports/${view.id}/decisions`, { decisions }));
    } catch (err) {
      setError(errorOf(err, 'Could not save that choice.'));
    } finally {
      setBusy(false);
    }
  };

  // Step 3: predict only once every field is resolved. The server validates again before running the model.
  // The patient corrects a value they answered or approved. The server keeps the old value in the history.
  const saveCorrection = async () => {
    if (!result?.report_id || !correcting) return;
    setBusy(true);
    setError('');
    try {
      const res = await postJSON<{ status: string; provenance: ProvenanceRow[] }>(
        `/api/v1/missing-data/reports/${result.report_id}/corrections`,
        { field: correcting.field, value: correcting.value },
      );
      setResult({ ...result, provenance: res.provenance, report_status: res.status });
      setStaleNote(res.status === 'stale');
      setCorrecting(null);
    } catch (err) {
      setError(errorOf(err, 'Could not save the correction.'));
    } finally {
      setBusy(false);
    }
  };

  const predict = async () => {
    if (!view) return;
    setBusy(true);
    setError('');
    setStaleNote(false);
    setCorrecting(null);
    try {
      const res = await postJSON<PredictionResult>(`/api/v1/missing-data/reports/${view.id}/predict`, {});
      setResult(res);
      setView(await getJSON<MissingDataView>(`/api/v1/missing-data/reports/${view.id}`));
    } catch (err) {
      setError(errorOf(err, 'Could not calculate the probability.'));
    } finally {
      setBusy(false);
    }
  };

  const loadCard = async () => {
    if (!detail) return;
    setShowCard(true);
    if (card !== null) return;
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/v1/models/${detail.key}/card`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error('card');
      setCard(await res.text());
    } catch {
      setCard('The model card could not be loaded.');
    }
  };

  const bars = useMemo(() => {
    if (!result?.probabilities) return [];
    return Object.entries(result.probabilities).sort((a, b) => b[1] - a[1]);
  }, [result]);

  const selectedItem = catalog?.find((m) => m.key === selected) ?? null;

  return (
    <Modal open={open} title="Disease models" onClose={onClose} wide>
      <p className="muted" style={{ marginTop: 0 }}>
        Trained on public datasets. These are research prototypes, not diagnostic tools. Each result shows the model's status and
        the limitations on its card.
      </p>

      {error && <p className="error-text" role="alert">{error}</p>}

      {!selected && (
        <div className="list-grid" style={{ display: 'grid', gap: '0.8rem', gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))' }}>
          {!catalog && !error && <p className="muted">Loading models…</p>}
          {catalog?.map((m, i) => (
            <motion.button
              key={m.key}
              className="chip"
              style={{ textAlign: 'left', padding: '1rem', display: 'grid', gap: '0.4rem', cursor: 'pointer' }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              onClick={() => setSelected(m.key)}
            >
              <strong>{humanize(m.key)}</strong>
              <span className="pill" style={{ justifySelf: 'start' }}>
                {m.status === 'research' ? 'Research prototype' : 'Limited: do not use'}
              </span>
              <span className="muted" style={{ fontSize: '0.85rem' }}>
                {m.task === 'binary' ? 'Binary' : `${m.classes.length} classes`} · {m.feature_count} inputs · {m.n_rows.toLocaleString()} rows
              </span>
              <span style={{ fontSize: '0.85rem' }}>
                {m.headline_metric.metric === 'roc_auc' ? 'ROC AUC' : 'Macro AUC'} {m.headline_metric.value.toFixed(3)} (95% CI{' '}
                {m.headline_metric.ci95[0].toFixed(3)}–{m.headline_metric.ci95[1].toFixed(3)})
              </span>
            </motion.button>
          ))}
        </div>
      )}

      {selected && (
        <div>
          <button className="btn btn-ghost" style={{ marginBottom: '1rem' }} onClick={() => { setSelected(null); setDetail(null); }}>
            ← All models
          </button>
          {!detail && !error && <p className="muted">Loading…</p>}
          {selectedItem && (
            <div style={{ marginBottom: '1rem' }}>
              <h4 style={{ margin: '0 0 0.3rem' }}>{humanize(selectedItem.key)}</h4>
              <p className="muted" style={{ margin: 0, fontSize: '0.9rem' }}>{selectedItem.status_reason}</p>
              <button className="btn btn-ghost" style={{ marginTop: '0.6rem' }} onClick={loadCard}>Read the model card</button>
            </div>
          )}

          {showCard && (
            <pre className="formatted" style={{ whiteSpace: 'pre-wrap', maxHeight: 320, overflow: 'auto', padding: '1rem', background: '#f7fbfb', borderRadius: 12, fontSize: '0.82rem' }}>
              {card ?? 'Loading card…'}
            </pre>
          )}

          {detail && (
            <form onSubmit={checkInfo}>
              <p className="muted" style={{ fontSize: '0.85rem' }}>
                Fill in what you know. Leave a field blank if you do not know it: the review below will offer anything found in your
                earlier records, and ask you about the rest.
              </p>
              <p className="muted" style={{ fontSize: '0.8rem', marginTop: 0 }}>
                Binary fields use 1 or 0 as recorded in the dataset (the card explains each field).
              </p>
              <div style={{ display: 'grid', gap: '0.8rem', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
                {detail.features.map((f) => (
                  <div className="field" key={f.name} style={{ marginBottom: 0 }}>
                    <label htmlFor={`f-${f.name}`}>{humanize(f.name)}</label>
                    {f.type === 'categorical' ? (
                      <select id={`f-${f.name}`} className="input" value={values[f.name] ?? ''} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}>
                        <option value="">Not answered</option>
                        {f.options?.map((o) => <option key={o} value={o}>{o}</option>)}
                      </select>
                    ) : f.type === 'binary' ? (
                      <select id={`f-${f.name}`} className="input" value={values[f.name] ?? ''} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}>
                        <option value="">Not answered</option>
                        <option value="1">1</option>
                        <option value="0">0</option>
                      </select>
                    ) : (
                      <input
                        id={`f-${f.name}`}
                        className="input"
                        type="number"
                        step="any"
                        min={f.min}
                        max={f.max}
                        placeholder="Not answered"
                        value={values[f.name] ?? ''}
                        onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                      />
                    )}
                  </div>
                ))}
              </div>
              <button className="btn btn-primary" type="submit" disabled={busy} style={{ marginTop: '1.2rem' }}>
                {busy ? 'Checking…' : 'Check my information'}
              </button>
            </form>
          )}

          {view && (
            <MissingDataReview view={view} busy={busy} error={error} onDecide={decide} onPredict={predict} canPredict />
          )}

          {result && (
            <motion.div ref={resultRef} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={{ marginTop: '1.5rem' }} aria-live="polite">
              {result.outcome === 'incomplete' ? (
                <>
                  <h4 style={{ marginBottom: '0.5rem' }}>No estimate yet</h4>
                  <p className="error-text">{result.message}</p>
                  {(result.unresolved_fields?.length ?? 0) > 0 && (
                    <p className="muted" style={{ fontSize: '0.85rem' }}>
                      Still missing: {result.unresolved_fields!.map(humanize).join(', ')}
                    </p>
                  )}
                </>
              ) : (
                <>
                  <h4 style={{ marginBottom: '0.5rem' }}>
                    {result.task === 'binary' && result.probability_positive !== undefined
                      ? `Estimated probability of a positive result: ${(result.probability_positive * 100).toFixed(1)}%`
                      : `Most likely class: ${humanize(result.top_class ?? '')}`}
                  </h4>
                  <div style={{ display: 'grid', gap: '0.5rem', marginBottom: '0.8rem' }}>
                    {bars.map(([cls, p]) => (
                      <div key={cls} style={{ display: 'grid', gridTemplateColumns: '150px 1fr 60px', gap: '0.6rem', alignItems: 'center', fontSize: '0.9rem' }}>
                        <span>{humanize(cls)}</span>
                        <div style={{ background: '#e6f1f1', borderRadius: 999, height: 10, overflow: 'hidden' }}>
                          <motion.div style={{ height: '100%', background: 'var(--brand-500)' }} initial={{ width: 0 }} animate={{ width: `${p * 100}%` }} transition={{ duration: 0.6 }} />
                        </div>
                        <span style={{ textAlign: 'right' }}>{(p * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                  {result.explanation && <p style={{ fontSize: '0.92rem' }}>{result.explanation}</p>}
                  {result.status === 'limited' && (
                    <p className="error-text">Limited model: {result.status_reason}</p>
                  )}
                  {(result.safety_notes ?? []).map((n) => (
                    <p key={n} className="muted" style={{ fontSize: '0.85rem' }}>{n}</p>
                  ))}
                  {result.notice && <p className="error-text" style={{ fontSize: '0.88rem' }}>{result.notice}</p>}
                  {result.provenance && result.provenance.length > 0 && (
                    <details style={{ marginTop: '0.6rem' }}>
                      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Where each value came from</summary>
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', fontSize: '0.82rem', borderCollapse: 'collapse', marginTop: '0.5rem' }}>
                          <thead>
                            <tr style={{ textAlign: 'left' }}>
                              <th>Field</th><th>Value used</th><th>Source</th><th>Source date</th><th>How</th><th>Your decision</th><th></th>
                            </tr>
                          </thead>
                          <tbody>
                            {result.provenance.map((row, i) => (
                              <tr key={`${row.field}-${i}`} style={{ borderTop: '1px solid var(--line)' }}>
                                <td>{humanize(row.field)}</td>
                                <td>{row.final_value ?? '—'}</td>
                                <td>{row.source === 'patient' ? 'You' : 'Your earlier answer'}</td>
                                <td>{row.source_date ?? '—'}</td>
                                <td>{humanize(row.method)}</td>
                                <td>{row.approval}</td>
                                <td>
                                  {row.final_value !== null && row.approval !== 'unknown' && (
                                    <button className="btn btn-ghost" disabled={busy}
                                      onClick={() => setCorrecting({ field: row.field, value: row.final_value ?? '' })}>
                                      Correct
                                    </button>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </details>
                  )}
                  {staleNote && (
                    <div className="banner-err" style={{ marginTop: '0.6rem' }}>
                      You changed a value after this estimate was made. The estimate used the earlier value, so it is no longer current.
                      Start a new check to get an updated estimate.
                    </div>
                  )}
                  {correcting && (
                    <div style={{ display: 'grid', gap: '0.5rem', gridTemplateColumns: 'minmax(160px, 1fr) auto auto', alignItems: 'end', marginTop: '0.6rem' }}>
                      <div className="field" style={{ marginBottom: 0 }}>
                        <label htmlFor="correction-value">Corrected value for {humanize(correcting.field)}</label>
                        <input id="correction-value" className="input" value={correcting.value}
                          onChange={(e) => setCorrecting({ ...correcting, value: e.target.value })} />
                      </div>
                      <button className="btn btn-primary" disabled={busy || correcting.value.trim() === ''} onClick={saveCorrection}>
                        Save correction
                      </button>
                      <button className="btn btn-ghost" onClick={() => setCorrecting(null)}>Cancel</button>
                    </div>
                  )}
                  <p className="muted" style={{ fontSize: '0.8rem' }}>{result.disclaimer}</p>
                </>
              )}
            </motion.div>
          )}
        </div>
      )}
    </Modal>
  );
}
