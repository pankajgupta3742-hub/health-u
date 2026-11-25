export type View = 'portfolio' | 'login' | 'register' | 'app';

// null = the patient chose "Not sure". Undefined or '' = not answered yet. Neither is ever filled in for them.
export interface SymptomData {
  primary_symptom: string | null;
  severity_score: number | null;
  duration_category: string | null;
  frequency: string | null;
  age_group: string | null;
  breathlessness_level: string | null;
  vomiting_severity: string | null;
  fever_level: string | null;
  pain_type: string | null;
}

export interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  isNew?: boolean;
  suggestions?: string[];
}

export interface Chat {
  id: string;
  title: string;
  messages: ChatMessage[];
  timestamp: number;
}

export interface MissingProposal {
  id: string;
  field: string;
  value: string;
  source_date: string;
  age_days: number;
  status: 'pending' | 'too_old';
  confidence: 'high' | 'medium' | 'low';
  reasoning: string;
}

export interface TriageMissingData {
  missing_fields: string[];
  proposals: MissingProposal[];
  provenance: Record<string, { source: string; source_date?: string; approval?: string }>;
  created_at?: string | null;
}

export interface TriageResult {
  id?: string;
  created_at?: string;
  final_urgency: 'High' | 'Moderate' | 'Low' | 'N/A' | string;
  status: string;
  missing_data?: TriageMissingData | null;
  rule_output: { matching_rule: string; logic: string };
  ml_output: { urgency: string; confidence: number };
  ai_explanation: {
    narrative: string;
    recommendation: string;
    first_aid: string;
    medicine_info: string;
  };
}

export interface MedicineInfo {
  error?: string;
  medicine?: string;
  subtitle?: string;
  description?: string;
  uses?: string[];
  side_effects?: string[];
  precautions?: string[];
  warnings?: string[];
  tags?: string[];
  related_medicines?: string[];
}

export interface DictionaryInfo {
  error?: string;
  term?: string;
  phonetic?: string;
  simple_definition?: string;
  clinical_definition?: string;
  context?: string;
  related_terms?: string[];
}

export interface AuthUser {
  id: string;
  email: string;
  name: string;
}

export interface LabCandidate {
  test_name: string;
  value: string;
  unit: string;
  reference_range: string;
  source_line: string;
}

export interface LabResult {
  id: string;
  test_name: string;
  value: string;
  unit: string;
  reference_range: string;
  recorded_on: string | null;
  created_at: string;
}

export interface AssessmentSummary extends TriageResult {
  id: string;
  created_at: string;
  input: Record<string, string | number>;
}

export interface ModelCatalogItem {
  key: string;
  task: 'binary' | 'multiclass';
  classes: string[];
  status: 'research' | 'limited';
  status_reason: string;
  headline_metric: { metric: string; value: number; ci95: [number, number] };
  n_rows: number;
  feature_count: number;
  card_url: string;
}

export interface FeatureSpec {
  name: string;
  type: 'numeric' | 'binary' | 'categorical';
  default?: number | string | null;
  min?: number;
  max?: number;
  options?: string[];
}

export interface ModelDetail {
  key: string;
  metrics: Record<string, any>;
  features: FeatureSpec[];
  classes: string[];
  disclaimer: string;
}

export interface PredictionResult {
  model: string;
  task: 'binary' | 'multiclass';
  outcome: 'complete' | 'incomplete';
  probabilities?: Record<string, number>;
  top_class?: string;
  probability_positive?: number;
  positive_class?: string;
  decision_threshold?: number;
  status?: 'research' | 'limited';
  status_reason?: string;
  unknown_fields?: string[];
  unresolved_fields?: string[];
  safety_notes?: string[];
  explanation?: string;
  answered_count?: number;
  unknown_count?: number;
  insufficient_answers?: boolean;
  message?: string;
  notice?: string;
  disclaimer: string;
  report_id?: string;
  report_status?: string;
  provenance?: ProvenanceRow[];
}

export type FieldStatus = 'patient_entered' | 'missing' | 'invalid' | 'completed' | 'unknown';
export type ProposalAction = 'accept' | 'reject' | 'edit' | 'manual' | 'unknown';

export interface Proposal {
  id: string;
  category: 'retrieved' | 'derived' | 'inferred';
  value: string;
  source_date: string;
  age_days: number;
  reasoning: string;
  evidence: { record_id: string; source_date: string; original_value: string | null; description: string }[];
  confidence: 'high' | 'medium' | 'low';
  requires_confirmation: boolean;
  status: string;
  allowed_actions: ProposalAction[];
}

export interface ReviewField {
  name: string;
  type: 'numeric' | 'binary' | 'categorical';
  status: FieldStatus;
  final_value: string | null;
  detail: string;
  options?: string[];
  min?: number;
  max?: number;
  proposals: Proposal[];
  allowed_actions: ProposalAction[];
}

export interface MissingDataView {
  id: string;
  model: string;
  status: 'open' | 'predicted';
  fields: ReviewField[];
  unresolved_fields: string[];
  ready: boolean;
  counts: Record<string, number>;
  disclaimer: string;
}

export interface ProvenanceRow {
  field: string;
  original_value: string | null;
  final_value: string | null;
  source: string;
  source_date: string | null;
  method: string;
  approval: string;
  timestamp: string | null;
}
