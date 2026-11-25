import { useEffect, useState } from 'react';
import type { FieldStatus, MissingDataView, Proposal, ReviewField } from '../types';

export type Decision = { field: string; action: 'accept' | 'reject' | 'edit' | 'manual' | 'unknown'; proposal_id?: string; value?: string | number };

const humanize = (v: string) => v.replace(/_/g, ' ');

const CATEGORY_LABEL: Record<string, string> = {
  retrieved: 'Found in your earlier confirmed answers',
  derived: 'Calculated from your earlier confirmed answer',
  inferred: 'Suggested from context',
};

const STATUS_LABEL: Record<FieldStatus, string> = {
  patient_entered: 'Answered by you',
  completed: 'Completed',
  unknown: 'Marked unknown',
  missing: 'Missing',
  invalid: 'Needs correcting',
};

const STATUS_COLOR: Record<FieldStatus, string> = {
  patient_entered: '#0f766e',
  completed: '#0f766e',
  unknown: '#6b7280',
  missing: '#b45309',
  invalid: '#b91c1c',
};

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{ fontSize: '0.75rem', fontWeight: 700, color, border: `1px solid ${color}`, borderRadius: 999, padding: '0.1rem 0.55rem', whiteSpace: 'nowrap' }}>
      {label}
    </span>
  );
}

function ValueInput({ field, value, onChange }: { field: ReviewField; value: string; onChange: (v: string) => void }) {
  const id = `review-${field.name}`;
  if (field.type === 'categorical' || field.type === 'binary') {
    const options = field.type === 'binary' ? ['1', '0'] : field.options ?? [];
    return (
      <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Choose…</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  return (
    <input id={id} className="input" type="number" step="any" min={field.min} max={field.max} value={value}
      onChange={(e) => onChange(e.target.value)} placeholder={field.min !== undefined ? `${field.min} to ${field.max}` : ''} />
  );
}

function ProposalCard({ field, proposal, busy, onDecide }: {
  field: ReviewField; proposal: Proposal; busy: boolean; onDecide: (d: Decision[]) => void;
}) {
  const [editing, setEditing] = useState<'edit' | 'manual' | null>(null);
  const [draft, setDraft] = useState(proposal.value);
  const stale = proposal.status === 'too_old';
  const actions = proposal.allowed_actions;

  return (
    <div style={{ border: '1px solid var(--line)', borderRadius: 12, padding: '0.8rem', background: '#fbfefe', display: 'grid', gap: '0.45rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <strong>Suggested: {humanize(proposal.value)}</strong>
        <Badge label={`${proposal.confidence} confidence`} color={proposal.confidence === 'high' ? '#0f766e' : proposal.confidence === 'medium' ? '#b45309' : '#b91c1c'} />
        {stale && <Badge label="Too old to use" color="#b91c1c" />}
      </div>
      <div className="muted" style={{ fontSize: '0.85rem' }}>
        {CATEGORY_LABEL[proposal.category] ?? proposal.category}. Recorded on {proposal.source_date} ({proposal.age_days} days ago).
      </div>
      <div style={{ fontSize: '0.88rem' }}>{proposal.reasoning}</div>
      {proposal.requires_confirmation && !stale && (
        <div className="muted" style={{ fontSize: '0.8rem' }}>This is not used until you confirm it.</div>
      )}
      {stale && (
        <div className="muted" style={{ fontSize: '0.8rem' }}>This information is too old to reuse. Please answer the question again.</div>
      )}

      {editing ? (
        <div style={{ display: 'grid', gap: '0.5rem', gridTemplateColumns: 'minmax(160px, 1fr) auto auto' }}>
          <ValueInput field={field} value={draft} onChange={setDraft} />
          <button className="btn btn-primary" disabled={busy || draft === ''} onClick={() => {
            onDecide([{ field: field.name, action: editing, proposal_id: proposal.id, value: draft }]);
            setEditing(null);
          }}>Save</button>
          <button className="btn btn-ghost" onClick={() => setEditing(null)}>Cancel</button>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {actions.includes('accept') && (
            <button className="btn btn-primary" disabled={busy} onClick={() => onDecide([{ field: field.name, action: 'accept', proposal_id: proposal.id }])}>
              Use this
            </button>
          )}
          {actions.includes('edit') && (
            <button className="btn btn-ghost" disabled={busy} onClick={() => { setDraft(proposal.value); setEditing('edit'); }}>
              Edit value
            </button>
          )}
          {actions.includes('reject') && (
            <button className="btn btn-ghost" disabled={busy} onClick={() => onDecide([{ field: field.name, action: 'reject', proposal_id: proposal.id }])}>
              Not this
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function MissingDataReview({ view, busy, error, onDecide, onPredict, canPredict }: {
  view: MissingDataView;
  busy: boolean;
  error: string;
  onDecide: (decisions: Decision[]) => void;
  onPredict: () => void;
  canPredict: boolean;
}) {
  // Drafts for fields that have no suggestion: the patient types an answer, or marks it unknown.
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  useEffect(() => setDrafts({}), [view.id]);

  const open = view.fields.filter((f) => f.status === 'missing' || f.status === 'invalid');
  const counts = view.counts;

  return (
    <section aria-label="Missing information review" style={{ marginTop: '1.2rem', borderTop: '1px solid var(--line)', paddingTop: '1rem' }}>
      <h4 style={{ margin: '0 0 0.3rem' }}>Missing information review</h4>
      <p className="muted" style={{ fontSize: '0.85rem', marginTop: 0 }}>
        Nothing is filled in unless you confirm it. Suggestions come only from your own earlier answers.
        {' '}{counts.patient_entered ?? 0} answered by you · {counts.completed ?? 0} completed · {counts.unknown ?? 0} unknown · {open.length} still to answer.
      </p>
      {error && <p className="error-text" role="alert">{error}</p>}

      <div style={{ display: 'grid', gap: '0.7rem' }}>
        {view.fields.map((f) => (
          <div key={f.name} style={{ display: 'grid', gap: '0.45rem', paddingBottom: '0.7rem', borderBottom: '1px dashed var(--line)' }}>
            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 600 }}>{humanize(f.name)}</span>
              <Badge label={STATUS_LABEL[f.status]} color={STATUS_COLOR[f.status]} />
              {(f.status === 'completed' || f.status === 'patient_entered') && f.final_value !== null && (
                <span className="muted" style={{ fontSize: '0.88rem' }}>Value: {humanize(f.final_value)}</span>
              )}
            </div>
            {f.detail && (f.status === 'invalid') && <div className="error-text" style={{ fontSize: '0.85rem' }}>{f.detail}</div>}

            {(f.status === 'missing' || f.status === 'invalid') && (
              <>
                {f.proposals.map((p) => (
                  <ProposalCard key={p.id} field={f} proposal={p} busy={busy} onDecide={onDecide} />
                ))}
                {f.allowed_actions.length > 0 && (
                  <div style={{ display: 'grid', gap: '0.5rem', gridTemplateColumns: 'minmax(160px, 1fr) auto auto', alignItems: 'end' }}>
                    <ValueInput field={f} value={drafts[f.name] ?? ''} onChange={(v) => setDrafts({ ...drafts, [f.name]: v })} />
                    <button className="btn btn-ghost" disabled={busy || !(drafts[f.name] ?? '').trim()}
                      onClick={() => onDecide([{ field: f.name, action: 'manual', value: drafts[f.name] }])}>
                      Save my answer
                    </button>
                    <button className="btn btn-ghost" disabled={busy} onClick={() => onDecide([{ field: f.name, action: 'unknown' }])}>
                      I don't know
                    </button>
                  </div>
                )}
              </>
            )}
            {f.status === 'unknown' && (
              <div className="muted" style={{ fontSize: '0.85rem' }}>
                The model will handle this field with its own missing-value method, and the result will say so.
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center', flexWrap: 'wrap', marginTop: '1rem' }}>
        <button className="btn btn-primary" disabled={busy || !view.ready || !canPredict} onClick={onPredict}>
          {busy ? 'Calculating…' : 'Calculate probability'}
        </button>
        {!view.ready && (
          <span className="muted" style={{ fontSize: '0.85rem' }}>Answer or mark each remaining question before calculating.</span>
        )}
      </div>
    </section>
  );
}
