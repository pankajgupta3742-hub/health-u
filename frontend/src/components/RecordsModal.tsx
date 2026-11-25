import { useEffect, useState } from 'react';
import { FileDown, FileUp, Trash2 } from 'lucide-react';
import Modal from './Modal';
import { ApiError, deleteRequest, downloadFile, getJSON, postJSON, uploadFile } from '../api';
import type { AssessmentSummary, LabCandidate, LabResult } from '../types';

type Tab = 'assessments' | 'labs';

interface Draft extends LabCandidate {
  keep: boolean;
}

const humanize = (v: unknown) => String(v ?? '').replace(/_/g, ' ');

interface GapReport {
  missing_fields: string[];
  provenance: Record<string, Record<string, unknown>> | Array<Record<string, unknown>>;
  created_at: string | null;
}

function errorOf(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

export default function RecordsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>('assessments');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const [assessments, setAssessments] = useState<AssessmentSummary[] | null>(null);
  const [labs, setLabs] = useState<LabResult[] | null>(null);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [fileNote, setFileNote] = useState('');
  // Per-assessment missing-data report, loaded when the patient opens "Data gaps".
  const [gapsFor, setGapsFor] = useState<string | null>(null);
  const [gaps, setGaps] = useState<Record<string, GapReport>>({});

  useEffect(() => {
    if (!open) return;
    setError('');
    setDrafts(null);
    setFileNote('');
    loadAssessments();
    loadLabs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const loadAssessments = async () => {
    try {
      setAssessments(await getJSON<AssessmentSummary[]>('/api/v1/assessments'));
    } catch (err) {
      setError(errorOf(err, 'Could not load your assessments.'));
    }
  };

  const loadLabs = async () => {
    try {
      setLabs(await getJSON<LabResult[]>('/api/v1/lab-results'));
    } catch (err) {
      setError(errorOf(err, 'Could not load your lab results.'));
    }
  };

  const toggleGaps = async (id: string) => {
    if (gapsFor === id) return setGapsFor(null);
    setGapsFor(id);
    if (gaps[id]) return;
    try {
      const report = await getJSON<GapReport>(`/api/v1/assessments/${id}/missing-data`);
      setGaps((g) => ({ ...g, [id]: report }));
    } catch (err) {
      setError(errorOf(err, 'Could not load the data-gap report.'));
    }
  };

  const exportData = async () => {
    setError('');
    try {
      await downloadFile('/api/v1/account/export', 'health-u-my-data.json');
    } catch (err) {
      setError(errorOf(err, 'Could not export your data.'));
    }
  };

  const downloadPdf = async (assessmentId: string) => {
    setBusy(true);
    setError('');
    try {
      const rep = await postJSON<{ id: string }>(`/api/v1/assessments/${assessmentId}/report`, {});
      await downloadFile(`/api/v1/reports/${rep.id}/download`, 'Health-U_Report.pdf');
    } catch (err) {
      setError(errorOf(err, 'Could not create the PDF report.'));
    } finally {
      setBusy(false);
    }
  };

  const removeAssessment = async (id: string) => {
    setError('');
    try {
      await deleteRequest(`/api/v1/assessments/${id}`);
      setAssessments((prev) => (prev ? prev.filter((a) => a.id !== id) : prev));
    } catch (err) {
      setError(errorOf(err, 'Could not delete this assessment.'));
    }
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError('');
    setDrafts(null);
    try {
      const res = await uploadFile<{ candidates: LabCandidate[]; note: string; filename: string }>(
        '/api/v1/documents/extract',
        file,
      );
      setFileNote(`${res.filename}: ${res.note}`);
      setDrafts(res.candidates.map((c) => ({ ...c, keep: true })));
    } catch (err) {
      setError(errorOf(err, 'Could not read this file.'));
    } finally {
      setBusy(false);
    }
  };

  const updateDraft = (i: number, patch: Partial<Draft>) =>
    setDrafts((prev) => (prev ? prev.map((d, idx) => (idx === i ? { ...d, ...patch } : d)) : prev));

  const saveDrafts = async () => {
    const chosen = (drafts ?? []).filter((d) => d.keep && d.value.trim());
    if (chosen.length === 0) {
      setError('Select at least one value to save.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await postJSON('/api/v1/lab-results', {
        results: chosen.map((d) => ({
          test_name: d.test_name,
          value: d.value,
          unit: d.unit,
          reference_range: d.reference_range,
        })),
      });
      setDrafts(null);
      setFileNote('');
      await loadLabs();
    } catch (err) {
      setError(errorOf(err, 'Could not save these values.'));
    } finally {
      setBusy(false);
    }
  };

  const removeLab = async (id: string) => {
    try {
      await deleteRequest(`/api/v1/lab-results/${id}`);
      setLabs((prev) => (prev ? prev.filter((l) => l.id !== id) : prev));
    } catch (err) {
      setError(errorOf(err, 'Could not delete this value.'));
    }
  };

  return (
    <Modal open={open} title="My records" onClose={onClose} wide>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'assessments'} className={tab === 'assessments' ? 'tab active' : 'tab'} onClick={() => setTab('assessments')}>
          Assessments
        </button>
        <button role="tab" aria-selected={tab === 'labs'} className={tab === 'labs' ? 'tab active' : 'tab'} onClick={() => setTab('labs')}>
          Lab results
        </button>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.6rem' }}>
        <button className="btn btn-ghost" style={{ fontSize: '0.85rem' }} onClick={exportData}>
          <FileDown size={14} /> Export my data (JSON)
        </button>
      </div>

      {error && <div className="error-text" role="alert">{error}</div>}

      {tab === 'assessments' && (
        <div>
          {assessments === null ? (
            <p className="muted">Loading…</p>
          ) : assessments.length === 0 ? (
            <p className="muted">No saved assessments yet. Completed symptom checks appear here.</p>
          ) : (
            assessments.map((a) => (
              <div className="record-row" key={a.id}>
                <div className="record-main">
                  <span className={`urgency-pill urgency-${a.final_urgency}`}>
                    <span className="dot" />
                    {a.final_urgency}
                  </span>
                  <div>
                    <strong>{humanize(a.input.primary_symptom)}</strong>
                    <small>
                      {new Date(a.created_at).toLocaleString()} · {a.rule_output?.matching_rule || a.status}
                    </small>
                  </div>
                </div>
                <div className="record-actions">
                  <button className="btn btn-ghost" onClick={() => toggleGaps(a.id)} aria-expanded={gapsFor === a.id}>
                    Data gaps
                  </button>
                  <button className="btn btn-ghost" disabled={busy} onClick={() => downloadPdf(a.id)} aria-label="Download PDF">
                    <FileDown size={15} /> PDF
                  </button>
                  <button className="btn btn-ghost" onClick={() => removeAssessment(a.id)} aria-label="Delete assessment">
                    <Trash2 size={15} />
                  </button>
                </div>
                {gapsFor === a.id && (
                  <div className="gap-panel" style={{ width: '100%', marginTop: 8, fontSize: '0.9rem' }}>
                    {!gaps[a.id] ? (
                      <p className="muted">Loading…</p>
                    ) : gaps[a.id].missing_fields.length === 0 && Object.keys(gaps[a.id].provenance || {}).length === 0 ? (
                      <p className="muted">No data gaps were recorded for this assessment.</p>
                    ) : (
                      <>
                        {gaps[a.id].missing_fields.length > 0 && (
                          <p>
                            <strong>Not provided at the time:</strong>{' '}
                            {gaps[a.id].missing_fields.map(humanize).join(', ')}
                          </p>
                        )}
                        {Object.keys(gaps[a.id].provenance || {}).length > 0 && (
                          <p className="muted">
                            Values used and where they came from are recorded for this assessment.
                          </p>
                        )}
                        <p className="muted">
                          Recorded {gaps[a.id].created_at ? new Date(gaps[a.id].created_at as string).toLocaleString() : 'n/a'}
                        </p>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {tab === 'labs' && (
        <div>
          <p className="muted" style={{ marginTop: 0 }}>
            Upload a text-based PDF or .txt lab report. The file is read in memory and not stored. Only the values you confirm are saved.
          </p>
          <label className="upload-box">
            <FileUp size={18} />
            <span>{busy ? 'Reading file…' : 'Choose a PDF or .txt file'}</span>
            <input
              type="file"
              accept="application/pdf,text/plain,.pdf,.txt"
              disabled={busy}
              onChange={(e) => onFile(e.target.files?.[0])}
              style={{ display: 'none' }}
            />
          </label>

          {drafts && (
            <div className="draft-box">
              {fileNote && <p className="muted" style={{ marginTop: 0 }}>{fileNote}</p>}
              {drafts.length === 0 ? (
                <p className="muted">No lab values were recognised. You can still review the file yourself.</p>
              ) : (
                drafts.map((d, i) => (
                  <div className="draft-row" key={`${d.test_name}-${i}`}>
                    <input type="checkbox" checked={d.keep} onChange={(e) => updateDraft(i, { keep: e.target.checked })} aria-label={`Keep ${d.test_name}`} />
                    <div className="draft-name">
                      <strong>{d.test_name}</strong>
                      <small title={d.source_line}>From: {d.source_line}</small>
                    </div>
                    <input className="input draft-input" value={d.value} onChange={(e) => updateDraft(i, { value: e.target.value })} aria-label={`${d.test_name} value`} />
                    <input className="input draft-input" value={d.unit} placeholder="Unit" onChange={(e) => updateDraft(i, { unit: e.target.value })} aria-label={`${d.test_name} unit`} />
                  </div>
                ))
              )}
              {drafts.length > 0 && (
                <button className="btn btn-primary" disabled={busy} onClick={saveDrafts} style={{ marginTop: 14 }}>
                  Save selected values
                </button>
              )}
            </div>
          )}

          <h4 style={{ marginTop: 26 }}>Saved values</h4>
          {labs === null ? (
            <p className="muted">Loading…</p>
          ) : labs.length === 0 ? (
            <p className="muted">Nothing saved yet.</p>
          ) : (
            labs.map((l) => (
              <div className="record-row" key={l.id}>
                <div className="record-main">
                  <div>
                    <strong>{l.test_name}</strong>
                    <small>
                      {l.value} {l.unit} {l.reference_range && `(ref ${l.reference_range})`} · saved {new Date(l.created_at).toLocaleDateString()}
                    </small>
                  </div>
                </div>
                <div className="record-actions">
                  <button className="btn btn-ghost" onClick={() => removeLab(l.id)} aria-label={`Delete ${l.test_name}`}>
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </Modal>
  );
}
