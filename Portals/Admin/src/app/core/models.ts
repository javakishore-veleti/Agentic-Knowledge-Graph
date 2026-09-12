/** TypeScript mirrors of Libraries/python/akg-contracts.
 *
 * These are hand-mirrored today. They must be generated from the JSON Schema exports
 * before the portal ships, or the two definitions will drift -- which is the exact
 * failure the single-contracts-package rule exists to prevent (ADR-006). */

export type TechStack =
  | 'airflow'
  | 'container_apps_job'
  | 'azure_functions'
  | 'azure_kafka_consumer'
  | 'aws_step_functions'
  | 'aws_lambda'
  | 'aws_kafka_consumer';

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
  return {
    airflow: 'Airflow',
    container_apps_job: 'Container Apps Job',
    azure_functions: 'Azure Functions',
    azure_kafka_consumer: 'Azure Kafka',
    aws_step_functions: 'Step Functions',
    aws_lambda: 'Lambda',
    aws_kafka_consumer: 'AWS Kafka',
  }[t];
}
