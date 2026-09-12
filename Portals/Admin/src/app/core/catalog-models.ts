/** TypeScript mirrors of the DataCatalog DTOs (Middleware/data-catalog).
 *
 * Hand-mirrored for now. These must be generated from the service's OpenAPI schema
 * before release, or the two definitions drift -- the failure the single-contracts rule
 * exists to prevent. */

export interface PageDto {
  total: number;
  limit: number;
  next_cursor: string | null;
}

export interface Paged<T> {
  page: PageDto;
  items: T[];
}

export interface DomainDto {
  domain_id: string;
  code: string;
  name: string;
  description: string;
  created_at: string;
}

/** Source data at a version. Immutable once acquired: a new version is a new row, so a
 *  MIO built last month can still name exactly what it read. Carries no counts and no
 *  validation state -- those describe the produced artifact, not the source. */
export interface DatasetDto {
  dataset_id: string;
  domain_id: string;
  code: string;
  name: string;
  description: string;
  source_version: string;
  adapter: string;
  sub_domain: string;
  created_at: string;
}

export type MioState = 'draft' | 'building' | 'ready' | 'live' | 'rejected' | 'retired';

/** Managed Informational Object: the produced, project-like artifact. */
export interface MioDto {
  mio_id: string;
  domain_id: string;
  domain_code: string;
  code: string;
  name: string;
  tech_stack: string;
  state: MioState;
  pinned_version: string | null;
  documents_count: number;
  edges_count: number;
  size_bytes: number;
  validations: Record<string, boolean>;
  /** False when any check failed AND when nothing was checked at all. */
  validations_pass: boolean;
  dataset_count: number;
  workflow_count: number;
  instance_count: number;
  has_cdc: boolean;
  generated_mio_count: number;
  last_exec_at: string | null;
  created_at: string;
  updated_at: string;
}

export type InstanceKind = 'historical' | 'realtime' | 'cdc';

export interface DataInstanceDto {
  data_instance_id: string;
  mio_id: string;
  kind: InstanceKind;
  label: string;
  description: string;
  state: string;
  /** Only ever set on a cdc instance, by database constraint. */
  stream_cursor: string | null;
  created_at: string;
  updated_at: string;
}

export interface DataInstancesResp extends Paged<DataInstanceDto> {
  /** A MIO has at most one, enforced by a partial unique index. */
  cdc_instance_id: string | null;
}

export interface DataInstanceExecDto {
  data_instance_exec_id: string;
  data_instance_id: string;
  status: string;
  input_tech: string | null;
  output_tech: string | null;
  input_data_json: unknown[];
  output_data_json: unknown[];
  wf_execs_json: unknown[];
  produced_mio_id: string | null;
  trace_id: string;
  env: string;
  requested_by: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

/** Where a technology lives. No credential field exists here by design; secret_ref names
 *  a Key Vault entry, and the secret never enters the catalog. */
export interface AppEndpointDto {
  app_endpoint_id: string;
  code: string;
  name: string;
  tech_stack: string;
  env: string;
  host: string;
  port: number | null;
  database: string | null;
  options: Record<string, unknown>;
  secret_ref: string | null;
  is_active: boolean;
}

export interface MioLineageEdgeDto {
  mio_id: string;
  code: string;
  name: string;
  data_instance_exec_id: string | null;
}

export interface MioLineageResp {
  mio_id: string;
  produced_from: MioLineageEdgeDto[];
  generated: MioLineageEdgeDto[];
}

export function mioStateChip(s: MioState): string {
  return {
    live: 'chip chip-ok',
    ready: 'chip chip-run',
    building: 'chip chip-warn',
    draft: 'chip chip-neutral',
    rejected: 'chip chip-fail',
    retired: 'chip chip-neutral',
  }[s];
}

export function instanceKindChip(k: InstanceKind): string {
  return k === 'cdc' ? 'chip chip-run' : k === 'realtime' ? 'chip chip-ok' : 'chip chip-neutral';
}

export function techLabel(t: string): string {
  return ({
    csr_graph: 'CSR graph',
    pgvector: 'pgvector',
    opensearch: 'OpenSearch',
    parquet_tables: 'Parquet',
    blob_prefix: 'Blob',
    postgres: 'Postgres',
  } as Record<string, string>)[t] ?? t;
}

export function humanBytes(n: number): string {
  if (!n) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}
