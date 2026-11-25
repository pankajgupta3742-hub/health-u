import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, ArrowLeft, ArrowRight, Check, CheckCircle2, Download, RotateCcw } from 'lucide-react';
import { ApiError, downloadFile, postJSON } from '../api';
import type { MissingProposal, SymptomData, TriageResult } from '../types';

type Accepted = { id: string; value: string; date: string };
const TRIAGE_KEYS = [
  'primary_symptom', 'severity_score', 'duration_category', 'frequency', 'age_group',
  'breathlessness_level', 'vomiting_severity', 'fever_level', 'pain_type',
] as const;

export const INITIAL_DATA: SymptomData = {
  primary_symptom: null,
  severity_score: null,
  duration_category: null,
  frequency: null,
  age_group: null,
  breathlessness_level: null,
  vomiting_severity: null,
  fever_level: null,
  pain_type: null,
};

const SYMPTOMS = [
  { id: 'chest_pain', label: 'Chest pain' },
  { id: 'shortness_of_breath', label: 'Shortness of breath' },
  { id: 'fever', label: 'Fever' },
  { id: 'vomiting', label: 'Vomiting' },
  { id: 'headache', label: 'Headache' },
  { id: 'abdominal_pain', label: 'Abdominal pain' },
  { id: 'sore_throat', label: 'Sore throat' },
  { id: 'cough', label: 'Cough' },
  { id: 'dizziness', label: 'Dizziness' },
];

const DURATIONS = [
  { id: 'short', label: 'Less than 1 day' },
  { id: 'medium', label: '1–3 days' },
  { id: 'long', label: 'More than 3 days' },
];

const FREQUENCIES = [
  { id: 'rare', label: 'First time' },
  { id: 'frequent', label: 'Recurring' },
  { id: 'persistent', label: 'Constant' },
];

const AGES = [
  { id: 'child', label: 'Under 18' },
  { id: 'adult', label: '18–60' },
  { id: 'elderly', label: '60 and over' },
];

const TOTAL_STEPS = 6;

const labelOf = (list: { id: string; label: string }[], id: string) => list.find((x) => x.id === id)?.label ?? id;
const humanize = (s: string) => s.replace(/_/g, ' ');

interface Props {
  onExit: () => void;
}

export default function Triage({ onExit }: Props) {
  const [step, setStep] = useState(1); // 1–6 questions, 7 review, 8 result
  const [dir, setDir] = useState(1);
  const [data, setData] = useState<SymptomData>(INITIAL_DATA);
  const [decided, setDecided] = useState<Record<string, boolean>>({}); // answered or "Not sure"
  const [accepted, setAccepted] = useState<Record<string, Accepted>>({}); // earlier answers the patient accepted
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TriageResult | null>(null);
  const [error, setError] = useState('');
  const [reportLoading, setReportLoading] = useState(false);

  // Recording an answer also drops any earlier answer accepted for that field, so the two can never clash.
  const set = <K extends keyof SymptomData>(key: K, value: SymptomData[K]) => {
    setData((prev) => ({ ...prev, [key]: value }));
    setDecided((d) => ({ ...d, [key]: true }));
    setAccepted((a) => {
      if (!(key in a)) return a;
      const { [key]: _drop, ...rest } = a;
      return rest;
    });
  };
  const pickOrUnsure = (key: keyof SymptomData, v: string) => set(key, v === 'unsure' ? null : v);
  const cur = (key: keyof SymptomData): string => {
    const v = data[key];
    if (v === null || v === undefined || v === '') return decided[key] ? 'unsure' : '';
    return String(v);
  };

  const canNext =
    (step === 1 && !!decided.primary_symptom) ||
    (step === 2 && !!decided.severity_score) ||
    (step === 3 && !!decided.duration_category) ||
    (step === 4 && !!decided.frequency) ||
    (step === 5 && !!decided.breathlessness_level && !!decided.vomiting_severity && !!decided.fever_level && !!decided.pain_type) ||
    (step === 6 && !!decided.age_group);

  // Only real answers are sent. Accepted earlier answers are sent as ids, never as values.
  const buildPayload = () => {
    const out: Record<string, unknown> = {};
    for (const k of TRIAGE_KEYS) {
      if (accepted[k]) continue;
      const v = data[k];
      if (v !== null && v !== undefined && v !== '') out[k] = v;
    }
    if (Object.keys(accepted).length) {
      out.accepted = Object.fromEntries(Object.entries(accepted).map(([k, a]) => [k, a.id]));
    }
    return out;
  };

  const acceptProposal = (p: MissingProposal) => {
    setAccepted((a) => ({ ...a, [p.field]: { id: p.id, value: p.value, date: p.source_date } }));
    setResult(null);
    setError('');
    setDir(1);
    setStep(7);
  };

  // What the review table shows for one field: the answer, an accepted earlier answer, "Not sure" or "Not answered".
  const shown = (key: keyof SymptomData, fmt: (v: string) => string) => {
    const a = accepted[key];
    if (a) return `${fmt(a.value)} (earlier answer from ${a.date}, accepted by you)`;
    const v = data[key];
    if (v === null || v === undefined || v === '') return decided[key] ? 'Not sure' : 'Not answered';
    return fmt(String(v));
  };

  const go = (n: number) => {
    setDir(n > step ? 1 : -1);
    setStep(n);
  };

  const runTriage = async () => {
    setLoading(true);
    setError('');
    try {
      const json = await postJSON<TriageResult>('/api/v1/assessments', buildPayload());
      setResult(json);
      setDir(1);
      setStep(8);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = async () => {
    if (!result?.id) return;
    setReportLoading(true);
    try {
      const rep = await postJSON<{ id: string }>(`/api/v1/assessments/${result.id}/report`, {});
      await downloadFile(`/api/v1/reports/${rep.id}/download`, 'Health-U_Report.pdf');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the PDF report.');
    } finally {
      setReportLoading(false);
    }
  };

  const restart = () => {
    setData(INITIAL_DATA);
    setDecided({});
    setAccepted({});
    setResult(null);
    setError('');
    go(1);
  };

  const isContradiction = result?.status === 'Contradiction Detected';
  const isIncomplete = result?.status?.startsWith('Incomplete') ?? false;
  const mlAgreed = result?.status === 'Agreement';

  return (
    <div className="triage">
      <button className="back-link" onClick={onExit}>
        <ArrowLeft size={16} /> Back to chat
      </button>

      {step <= TOTAL_STEPS && (
        <div className="triage-card">
          <div className="progress-meta">
            <span>Step {step} of {TOTAL_STEPS}</span>
            <span>{Math.round((step / TOTAL_STEPS) * 100)}%</span>
          </div>
          <div className="progress">
            <motion.span
              initial={false}
              animate={{ width: `${(step / TOTAL_STEPS) * 100}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>

          <AnimatePresence mode="wait" custom={dir}>
            <motion.div
              key={step}
              custom={dir}
              initial={{ opacity: 0, x: dir * 36 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: dir * -36 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            >
              {step === 1 && (
                <>
                  <h2 className="q-title">What is your main symptom?</h2>
                  <p className="q-sub">Choose the one that bothers you most.</p>
                  <div className="options">
                    {SYMPTOMS.map((s) => (
                      <Option
                        key={s.id}
                        active={data.primary_symptom === s.id}
                        label={s.label}
                        onClick={() => set('primary_symptom', s.id)}
                      />
                    ))}
                    <Option label="Not sure" active={!!decided.primary_symptom && data.primary_symptom === null}
                      onClick={() => set('primary_symptom', null)} />
                  </div>
                </>
              )}

              {step === 2 && (
                <>
                  <h2 className="q-title">How severe is it?</h2>
                  <p className="q-sub">Rate from 1 (barely noticeable) to 10 (the worst you have felt).</p>
                  <div className="slider-wrap">
                    <div className="slider-value">
                      {data.severity_score === null ? (decided.severity_score ? 'Not sure' : 'Not answered') : `${data.severity_score}/10`}
                      <small>
                        {data.severity_score === null ? '' : data.severity_score < 4 ? 'Mild' : data.severity_score < 8 ? 'Moderate' : 'Severe'}
                      </small>
                    </div>
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={data.severity_score ?? 5}
                      onChange={(e) => set('severity_score', parseInt(e.target.value, 10))}
                      aria-label="Severity score"
                    />
                    <div style={{ marginTop: 8 }}>
                      <button type="button" className="btn btn-ghost" onClick={() => set('severity_score', null)}>Not sure</button>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)', fontSize: '0.85rem' }}>
                      <span>1 Mild</span><span>5 Moderate</span><span>10 Severe</span>
                    </div>
                  </div>
                </>
              )}

              {step === 3 && (
                <>
                  <h2 className="q-title">How long have you had it?</h2>
                  <p className="q-sub">This helps us judge how quickly it is changing.</p>
                  <div className="options">
                    {DURATIONS.map((d) => (
                      <Option key={d.id} active={data.duration_category === d.id} label={d.label} onClick={() => set('duration_category', d.id)} />
                    ))}
                    <Option label="Not sure" active={!!decided.duration_category && data.duration_category === null}
                      onClick={() => set('duration_category', null)} />
                  </div>
                </>
              )}

              {step === 4 && (
                <>
                  <h2 className="q-title">Have you had this before?</h2>
                  <p className="q-sub">Pick the option that best describes it.</p>
                  <div className="options">
                    {FREQUENCIES.map((f) => (
                      <Option key={f.id} active={data.frequency === f.id} label={f.label} onClick={() => set('frequency', f.id)} />
                    ))}
                    <Option label="Not sure" active={!!decided.frequency && data.frequency === null}
                      onClick={() => set('frequency', null)} />
                  </div>
                </>
              )}

              {step === 5 && (
                <>
                  <h2 className="q-title">Any other symptoms?</h2>
                  <p className="q-sub">Pick the closest answer for each. Choose "None" if it does not apply, or "Not sure".</p>

                  <div className="group-label">Shortness of breath</div>
                  <div className="options">
                    <Choice value={cur('breathlessness_level')} current={cur('breathlessness_level')} options={[['none', 'None'], ['mild', 'Mild'], ['severe', 'Severe'], ['unsure', 'Not sure']]} onPick={(v) => pickOrUnsure('breathlessness_level', v)} />
                  </div>

                  <div className="group-label">Vomiting</div>
                  <div className="options">
                    <Choice value={cur('vomiting_severity')} current={cur('vomiting_severity')} options={[['none', 'None'], ['mild', 'Mild'], ['severe', 'Severe'], ['unsure', 'Not sure']]} onPick={(v) => pickOrUnsure('vomiting_severity', v)} />
                  </div>

                  <div className="group-label">Fever</div>
                  <div className="options">
                    <Choice value={cur('fever_level')} current={cur('fever_level')} options={[['none', 'None'], ['mild', 'Mild'], ['high', 'High'], ['unsure', 'Not sure']]} onPick={(v) => pickOrUnsure('fever_level', v)} />
                  </div>

                  <div className="group-label">Type of pain</div>
                  <div className="options">
                    <Choice value={cur('pain_type')} current={cur('pain_type')} options={[['none', 'No pain'], ['dull', 'Dull ache'], ['sharp', 'Sharp'], ['unsure', 'Not sure']]} onPick={(v) => pickOrUnsure('pain_type', v)} />
                  </div>
                </>
              )}

              {step === 6 && (
                <>
                  <h2 className="q-title">What is your age group?</h2>
                  <p className="q-sub">Some conditions need closer attention at certain ages.</p>
                  <div className="options">
                    {AGES.map((a) => (
                      <Option key={a.id} active={data.age_group === a.id} label={a.label} onClick={() => set('age_group', a.id)} />
                    ))}
                    <Option label="Not sure" active={!!decided.age_group && data.age_group === null}
                      onClick={() => set('age_group', null)} />
                  </div>
                </>
              )}
            </motion.div>
          </AnimatePresence>

          <div className="step-actions">
            <button className="btn btn-ghost" onClick={() => go(step - 1)} disabled={step === 1}>
              <ArrowLeft size={16} /> Back
            </button>
            {step < TOTAL_STEPS ? (
              <motion.button
                className="btn btn-primary"
                disabled={!canNext}
                onClick={() => go(step + 1)}
                whileHover={{ scale: canNext ? 1.03 : 1 }}
                whileTap={{ scale: canNext ? 0.97 : 1 }}
              >
                Next <ArrowRight size={16} />
              </motion.button>
            ) : (
              <motion.button
                className="btn btn-primary"
                disabled={!canNext}
                onClick={() => go(7)}
                whileHover={{ scale: canNext ? 1.03 : 1 }}
                whileTap={{ scale: canNext ? 0.97 : 1 }}
              >
                Review answers <ArrowRight size={16} />
              </motion.button>
            )}
          </div>
        </div>
      )}

      {step === 7 && (
        <motion.div className="triage-card" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
          <h2 className="q-title" style={{ marginTop: 0 }}>Review your answers</h2>
          <p className="q-sub">Check everything before we run the assessment.</p>

          {error && <div className="banner-err"><AlertTriangle size={18} /> {error}</div>}

          <table className="review-table">
            <tbody>
              <tr><td>Main symptom</td><td>{shown('primary_symptom', (v) => labelOf(SYMPTOMS, v))}</td></tr>
              <tr><td>Severity</td><td>{shown('severity_score', (v) => `${v}/10`)}</td></tr>
              <tr><td>Duration</td><td>{shown('duration_category', (v) => labelOf(DURATIONS, v))}</td></tr>
              <tr><td>Frequency</td><td>{shown('frequency', (v) => labelOf(FREQUENCIES, v))}</td></tr>
              <tr><td>Shortness of breath</td><td>{shown('breathlessness_level', humanize)}</td></tr>
              <tr><td>Vomiting</td><td>{shown('vomiting_severity', humanize)}</td></tr>
              <tr><td>Fever</td><td>{shown('fever_level', humanize)}</td></tr>
              <tr><td>Type of pain</td><td>{shown('pain_type', humanize)}</td></tr>
              <tr><td>Age group</td><td>{shown('age_group', (v) => labelOf(AGES, v))}</td></tr>
            </tbody>
          </table>

          {(() => {
            const open = TRIAGE_KEYS.filter((k) => !accepted[k] && (data[k] === null || data[k] === '' || data[k] === undefined));
            return open.length > 0 ? (
              <p className="muted" style={{ fontSize: '0.88rem', marginTop: 12 }}>
                {open.length} answer{open.length > 1 ? 's are' : ' is'} not answered or marked "Not sure". The result will be
                incomplete: no urgency level is calculated from missing answers.
              </p>
            ) : null;
          })()}

          <div className="step-actions">
            <button className="btn btn-ghost" onClick={() => go(6)}>
              <ArrowLeft size={16} /> Edit answers
            </button>
            <motion.button
              className="btn btn-primary btn-lg"
              onClick={runTriage}
              disabled={loading}
              whileHover={{ scale: loading ? 1 : 1.03 }}
              whileTap={{ scale: loading ? 1 : 0.97 }}
            >
              {loading ? 'Analysing…' : 'Run assessment'} <ArrowRight size={16} />
            </motion.button>
          </div>
        </motion.div>
      )}

      {step === 8 && result && (
        <motion.div className="result-card" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
          {isIncomplete ? (
            <>
              <div className="banner-err"><AlertTriangle size={18} /> <strong>Some answers are missing.</strong></div>
              <p style={{ color: 'var(--ink-2)' }}>{result.ai_explanation.narrative}</p>
              <p style={{ color: 'var(--ink-2)' }}>
                Still missing: {(result.missing_data?.missing_fields ?? []).map((f) => f.replace(/_/g, ' ')).join(', ')}
              </p>
              {(result.missing_data?.proposals ?? []).length > 0 && (
                <div className="info-box">
                  <h4>Found in your earlier assessments</h4>
                  <p className="muted" style={{ fontSize: '0.85rem' }}>
                    These were not used. Nothing is filled in without your choice. Answer the questions instead.
                  </p>
                  <ul>
                    {(result.missing_data?.proposals ?? []).map((p) => (
                      <li key={p.id} style={{ marginBottom: 6 }}>
                        {p.field.replace(/_/g, ' ')}: {p.value.replace(/_/g, ' ')} (recorded {p.source_date}
                        {p.status === 'too_old' ? ', too old to use' : ''})
                        {p.status === 'pending' && (
                          <button type="button" className="btn btn-ghost" style={{ marginLeft: 8 }}
                            onClick={() => acceptProposal(p)}>Use this answer</button>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="step-actions">
                <button className="btn btn-ghost" onClick={() => go(6)}><ArrowLeft size={16} /> Edit answers</button>
                <button className="btn btn-primary" onClick={restart}><RotateCcw size={16} /> Start over</button>
              </div>
            </>
          ) : isContradiction ? (
            <>
              <div className="banner-err"><AlertTriangle size={18} /> <strong>Your answers don't match.</strong></div>
              <p style={{ color: 'var(--ink-2)' }}>{result.ai_explanation.narrative}</p>
              <div className="step-actions">
                <button className="btn btn-ghost" onClick={() => go(6)}><ArrowLeft size={16} /> Edit answers</button>
                <button className="btn btn-primary" onClick={restart}><RotateCcw size={16} /> Start over</button>
              </div>
            </>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                <div>
                  <div style={{ color: 'var(--muted)', fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>Your urgency level</div>
                  <motion.div
                    className={`urgency-pill urgency-${result.final_urgency}`}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ type: 'spring', stiffness: 220, damping: 16 }}
                  >
                    <span className="dot" /> {result.final_urgency} urgency
                  </motion.div>
                </div>
                <div style={{ fontSize: '0.9rem', color: 'var(--ink-2)', maxWidth: 300 }}>
                  {mlAgreed ? (
                    <span style={{ color: 'var(--low)', display: 'inline-flex', gap: 6, alignItems: 'center' }}><CheckCircle2 size={16} /> Rule and model agree</span>
                  ) : (
                    <span style={{ color: '#a86510' }}>The rules set this level. The secondary model suggested a different level, so the rule-based result is shown.</span>
                  )}
                </div>
              </div>

              <div className="result-grid">
                <div className="info-box">
                  <h4>Rule that applied</h4>
                  <p><strong>{result.rule_output.matching_rule}</strong></p>
                  <p style={{ marginTop: 6 }}>{result.rule_output.logic}</p>
                </div>
                <div className="info-box">
                  <h4>Next steps</h4>
                  <p>{result.ai_explanation.recommendation}</p>
                </div>
              </div>

              <div className="ai-box">
                <h4>Explanation</h4>
                <p style={{ color: 'var(--ink-2)' }}>{result.ai_explanation.narrative}</p>
              </div>

              <div className="result-grid">
                <div className="info-box">
                  <h4>First aid</h4>
                  <p>{result.ai_explanation.first_aid}</p>
                </div>
                <div className="info-box">
                  <h4>Medicine information</h4>
                  <p>{result.ai_explanation.medicine_info}</p>
                </div>
              </div>

              {error && <div className="banner-err" style={{ marginTop: 14 }}><AlertTriangle size={18} /> {error}</div>}

              <div className="step-actions">
                <button className="btn btn-ghost" onClick={restart}><RotateCcw size={16} /> New assessment</button>
                <motion.button
                  className="btn btn-primary"
                  onClick={downloadReport}
                  disabled={reportLoading}
                  whileHover={{ scale: reportLoading ? 1 : 1.03 }}
                  whileTap={{ scale: reportLoading ? 1 : 0.97 }}
                >
                  <Download size={16} /> {reportLoading ? 'Preparing PDF…' : 'Download PDF report'}
                </motion.button>
              </div>

              <p style={{ marginTop: 18, fontSize: '0.8rem', color: 'var(--muted)' }}>
                {new Date().toLocaleString()}. This is for information only and does not replace a medical assessment.
                If you feel this is an emergency, call your local emergency number now.
              </p>
            </>
          )}
        </motion.div>
      )}
    </div>
  );
}

function Option({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <motion.button
      type="button"
      className={`option ${active ? 'active' : ''}`}
      onClick={onClick}
      whileTap={{ scale: 0.98 }}
      aria-pressed={active}
    >
      <span className="tick">{active && <Check size={13} strokeWidth={3} />}</span>
      {label}
    </motion.button>
  );
}

function Choice({
  current,
  options,
  onPick,
}: {
  value: string;
  current: string;
  options: [string, string][];
  onPick: (v: string) => void;
}) {
  return (
    <>
      {options.map(([v, l]) => (
        <Option key={v} label={l} active={current === v} onClick={() => onPick(v)} />
      ))}
    </>
  );
}
