/** TypeScript mirrors of Libraries/python/akg-contracts.
 *
 * These are hand-mirrored today. They must be generated from the JSON Schema exports
 * before the portal ships, or the two definitions will drift -- which is the exact
 * failure the single-contracts-package rule exists to prevent (ADR-006). */

/** Execution model decides what the portal may offer: only a triggered run can be
 *  invoked. A stream has no run to start, and a human process is not finished by
 *  compute (ADR-014). */
export type ExecutionModel = 'triggered_run' | 'continuous' | 'human_process';

export type TechStack =
  // triggered runs
  | 'airflow' | 'container_apps_job' | 'azure_functions' | 'azure_data_factory'
  | 'azure_logic_apps' | 'aws_step_functions' | 'aws_lambda' | 'aws_emr' | 'aws_glue'
  | 'aws_batch' | 'databricks_job' | 'custom_api'
  // continuous: no discrete run
  | 'azure_kafka_consumer' | 'aws_kafka_consumer' | 'aws_kinesis' | 'azure_event_hubs'
  | 'spark_streaming'
  // human process
  | 'bpmn_camunda' | 'bpmn_flowable';

const CONTINUOUS: TechStack[] = [
  'azure_kafka_consumer', 'aws_kafka_consumer', 'aws_kinesis', 'azure_event_hubs',
  'spark_streaming',
];
const HUMAN: TechStack[] = ['bpmn_camunda', 'bpmn_flowable'];

export function executionModel(t: TechStack): ExecutionModel {
  if (CONTINUOUS.includes(t)) return 'continuous';
  if (HUMAN.includes(t)) return 'human_process';
  return 'triggered_run';
}

/** Invoking a stream would log a PENDING execution that never completes. */
export function isInvocable(t: TechStack): boolean {
  return executionModel(t) === 'triggered_run';
}

export type WorkflowStatus =
  | 'PENDING' | 'SUBMITTED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED';

export const TERMINAL: WorkflowStatus[] = ['SUCCEEDED', 'FAILED', 'CANCELLED'];

export interface WorkflowBatch {
  wf_batch_id: string;
  batch_name: string;
  batch_instance: string;
  domain: string;
  sub_domain: string;
  tech_stack: TechStack;
  status: WorkflowStatus;
  total_count: number;
  succeeded_count: number;
  failed_count: number;
  trace_id: string;
  tenant_id: string;
  env: string;
  requested_by?: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
}

export interface WorkflowExecution {
  exec_id: string;
  wf_batch_id?: string;
  domain: string;
  sub_domain: string;
  workflow: string;
  tech_stack: TechStack;
  /** Airflow dag_run_id, Step Functions ARN, Lambda request id. Absent until the
   *  engine accepts the submission -- which is how a failed submit stays visible. */
  wf_ref_id?: string;
  status: WorkflowStatus;
  input_data: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  error?: Record<string, unknown>;
  trace_id: string;
  tenant_id: string;
  env: string;
  requested_by?: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
}

/** A workflow the Admin portal may trigger. Note the absence of tech_stack: the portal
 *  cannot choose an engine, configuration does (ADR-008). */
export interface WorkflowDefinition {
  workflow: string;
  title: string;
  domain: string;
  sub_domain: string;
  description: string;
  /** Resolved server-side, shown read-only so an operator knows what will run. */
  runs_on: TechStack;
  params: WorkflowParam[];
}

export interface WorkflowParam {
  name: string;
  label: string;
  kind: 'text' | 'date' | 'select' | 'bool';
  options?: string[];
  default?: string | boolean;
  required: boolean;
  help?: string;
}

/** A corpus version whose ingestion completed and whose artifacts are pinnable. */
export interface DataSet {
  dataset_id: string;
  name: string;
  domain: string;
  sub_domain: string;
  source_version: string;
  ontology_version: string;
  documents: number;
  edges: number;
  embedded: number;
  /** live = an active release points at it. */
  state: 'live' | 'ready' | 'building' | 'rejected';
  graph_version: string;
  index_version: string;
  alignment_assert: boolean;
  source_recount: boolean;
  ingested_at: string;
  size_gb: number;
}

export function statusChip(s: WorkflowStatus): string {
  switch (s) {
    case 'SUCCEEDED': return 'chip chip-ok';
    case 'RUNNING':
    case 'SUBMITTED': return 'chip chip-run';
    case 'PENDING': return 'chip chip-warn';
    case 'FAILED': return 'chip chip-fail';
    default: return 'chip chip-neutral';
  }
}

export function stackLabel(t: TechStack): string {
  return ({
    airflow: 'Airflow',
    container_apps_job: 'Container Apps Job',
    azure_functions: 'Azure Functions',
    azure_data_factory: 'Data Factory',
    azure_logic_apps: 'Logic Apps',
    aws_step_functions: 'Step Functions',
    aws_lambda: 'Lambda',
    aws_emr: 'EMR',
    aws_glue: 'Glue',
    aws_batch: 'Batch',
    databricks_job: 'Databricks',
    custom_api: 'Custom API',
    azure_kafka_consumer: 'Azure Kafka',
    aws_kafka_consumer: 'AWS Kafka (MSK)',
    aws_kinesis: 'Kinesis',
    azure_event_hubs: 'Event Hubs',
    spark_streaming: 'Spark Streaming',
    bpmn_camunda: 'Camunda (BPMN)',
    bpmn_flowable: 'Flowable (BPMN)',
  } as Record<TechStack, string>)[t] ?? t;
}

/* ---- Quality gate and release control (PRD B B5) ---------------------- */

/** A reference arm. These run on every candidate and can never be selected as the
 *  winner: they exist to prove the measurement instrument still works. An oracle that
 *  stops scoring near-perfect, or a shuffled-label arm that scores above chance, means
 *  the harness is broken and the headline number is meaningless. */
export interface ReferenceArm {
  arm: 'oracle' | 'blind' | 'majority_class' | 'shuffled_label';
  accuracy: number;
  /** Range this arm must land in for the run to be trustworthy. */
  expected_min: number;
  expected_max: number;
}

export interface ErrorBudgetItem {
  cause: string;
  share: number;
  note: string;
}

export interface Release {
  release: string;
  created_at: string;
  state: 'live' | 'candidate' | 'rejected' | 'superseded';
  graph: string;
  index: string;
  ontology: string;
  calibration: string;
  test_accuracy: number;
  coverage: number;
  /** Control questions answered when they should have been refused. */
  leak: number;
  gold_in_top_16: number;
  /** Citations naming a document outside the admitted set. Must be zero. */
  unadmitted_citations: number;
  arms: ReferenceArm[];
  error_budget: ErrorBudgetItem[];
}

export function armLabel(a: ReferenceArm['arm']): string {
  return {
    oracle: 'Oracle',
    blind: 'Blind (no evidence)',
    majority_class: 'Majority class',
    shuffled_label: 'Shuffled labels',
  }[a];
}

export function armOk(a: ReferenceArm): boolean {
  return a.accuracy >= a.expected_min && a.accuracy <= a.expected_max;
}

/** The margin the gate actually optimises: coverage net of leak. */
export function margin(r: Release): number {
  return r.coverage - r.leak;
}

/** Every condition promotion requires. Returned as a list so the UI can show the
 *  operator exactly which one is blocking rather than a bare disabled button. */
export function gateFailures(r: Release, live?: Release): string[] {
  const out: string[] = [];
  for (const a of r.arms) {
    if (!armOk(a)) out.push(`${armLabel(a.arm)} arm outside tolerance (${(a.accuracy * 100).toFixed(1)}%)`);
  }
  if (r.unadmitted_citations > 0) out.push(`${r.unadmitted_citations} unadmitted citation(s)`);
  if (r.gold_in_top_16 < 0.95) out.push(`gold-in-top-16 ${(r.gold_in_top_16 * 100).toFixed(1)}% below 95%`);
  if (live) {
    if (r.test_accuracy < live.test_accuracy) out.push('accuracy below the live pin');
    if (margin(r) < margin(live)) out.push('margin below the live pin');
  }
  return out;
}

/* ---- Source trace explorer (PRD B B4) --------------------------------- */

export type CertRoute = 'co_annotation' | 'ontology_ancestry' | 'citation_adjacency' | 'uncertified';

export interface TraceConcept {
  concept_id: string;
  name: string;
  role: 'bridge' | 'filter' | 'ignore';
  is_check_tag: boolean;
}

export interface TraceCandidate {
  doc_id: string;
  title: string;
  dense_score: number;
  rerank_score?: number;
  route: CertRoute;
  reason: string;
  path: string[];
  retracted: boolean;
  quotable: boolean;
  admitted: boolean;
  cited: boolean;
}

export interface GateResult {
  gate: string;
  /** true = the question passed this gate. */
  passed: boolean;
  detail: string;
}

export interface Trace {
  answer_id: string;
  question: string;
  as_of?: string;
  trace_id: string;
  tenant_id: string;
  asked_at: string;
  concepts: TraceConcept[];
  candidates: TraceCandidate[];
  gates: GateResult[];
  posterior?: Record<string, number>;
  raw_confidence?: number;
  calibrated_confidence?: number;
  threshold: number;
  disposition: 'ANSWER' | 'REFUSE' | 'HUMAN_REVIEW';
  refusal_reason?: string;
  answer_text?: string;
  pins: { graph: string; index: string; ontology: string; calibration: string };
}

export function routeLabel(r: CertRoute): string {
  return {
    co_annotation: 'Co-annotation',
    ontology_ancestry: 'Ontology ancestry',
    citation_adjacency: 'Citation adjacency',
    uncertified: 'Uncertified',
  }[r];
}

export function routeChip(r: CertRoute): string {
  return r === 'uncertified' ? 'chip chip-warn' : 'chip chip-run';
}
