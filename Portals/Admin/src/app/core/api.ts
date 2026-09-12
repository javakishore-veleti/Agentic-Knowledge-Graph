import { Injectable, signal } from '@angular/core';
import {
  DataSet, TechStack, WorkflowBatch, WorkflowDefinition, WorkflowExecution, WorkflowStatus,
} from './models';

/** Mock data source.
 *
 * Every method here is the shape the FastAPI orchestrator will expose, so replacing this
 * with HttpClient is a body swap and not a signature change. Nothing in a component may
 * reach past this service. */
@Injectable({ providedIn: 'root' })
export class Api {
  readonly tenant = signal('reference');
  readonly env = signal('local');

  private readonly now = Date.now();
  private iso(minutesAgo: number): string {
    return new Date(this.now - minutesAgo * 60_000).toISOString();
  }

  datasets(): DataSet[] {
    return [
      {
        dataset_id: 'ds-pubmed-2026',
        name: 'PubMed annual baseline 2026',
        domain: 'biomedical', sub_domain: 'literature',
        source_version: 'pubmed-baseline-2026', ontology_version: 'mesh-2026',
        documents: 39_990_112, edges: 929_824_202, embedded: 28_300_441,
        state: 'live',
        graph_version: '2026.09.12-a3f9c1', index_version: '2026.09.12-7b21de',
        alignment_assert: true, source_recount: true,
        ingested_at: this.iso(60 * 26), size_gb: 412.7,
      },
      {
        dataset_id: 'ds-pubmed-2026-delta',
        name: 'PubMed daily delta · week 37',
        domain: 'biomedical', sub_domain: 'literature',
        source_version: 'pubmed-delta-2026w37', ontology_version: 'mesh-2026',
        documents: 84_221, edges: 1_904_776, embedded: 84_221,
        state: 'ready',
        graph_version: '2026.09.12-delta-4c', index_version: '2026.09.12-delta-4c',
        alignment_assert: true, source_recount: true,
        ingested_at: this.iso(95), size_gb: 1.4,
      },
      {
        dataset_id: 'ds-clinicaltrials',
        name: 'ClinicalTrials.gov registry',
        domain: 'biomedical', sub_domain: 'trials',
        source_version: 'ctgov-2026-09', ontology_version: 'mesh-2026',
        documents: 512_884, edges: 0, embedded: 512_884,
        state: 'building',
        graph_version: '—', index_version: '2026.09.12-ct-01',
        alignment_assert: false, source_recount: false,
        ingested_at: this.iso(22), size_gb: 6.8,
      },
      {
        dataset_id: 'ds-internal-kb',
        name: 'Internal engineering knowledge base',
        domain: 'enterprise', sub_domain: 'documentation',
        source_version: 'kb-2026-09-04', ontology_version: 'mesh-2026',
        documents: 18_402, edges: 41_339, embedded: 18_402,
        // Edge extraction ran through the generic adapter and the recount disagreed
        // with the CSR count, so this set is not promotable.
        state: 'rejected',
        graph_version: '2026.09.04-kb-02', index_version: '2026.09.04-kb-02',
        alignment_assert: true, source_recount: false,
        ingested_at: this.iso(60 * 190), size_gb: 0.9,
      },
    ];
  }

  workflowDefinitions(): WorkflowDefinition[] {
    return [
      {
        workflow: 'historical_ingest', title: 'Historical corpus ingest',
        domain: 'corpus', sub_domain: 'historical-ingest', runs_on: 'airflow',
        description:
          'Acquire, parse, link the ontology, build the CSR graph, embed, consolidate, ' +
          'and emit a manifest. Fans out one execution per source file.',
        params: [
          { name: 'source_version', label: 'Source version', kind: 'text', required: true,
            default: 'pubmed-baseline-2026' },
          { name: 'adapter', label: 'Adapter', kind: 'select', required: true,
            options: ['pubmed', 'generic-extraction'], default: 'pubmed',
            help: 'Edge-bearing sources parse directly; generic extraction reports cost separately.' },
          { name: 'smoke', label: 'Smoke run', kind: 'bool', required: false, default: true,
            help: 'Shrinks to 12 files. Use before spending GPU time.' },
        ],
      },
      {
        workflow: 'rebuild_index', title: 'Rebuild vector index',
        domain: 'corpus', sub_domain: 'index', runs_on: 'airflow',
        description: 'Re-embed and consolidate shards into one pinnable index.',
        params: [
          { name: 'source_version', label: 'Source version', kind: 'text', required: true },
          { name: 'model', label: 'Embedding model', kind: 'select', required: true,
            options: ['BAAI/bge-small-en-v1.5', 'BAAI/bge-base-en-v1.5'],
            default: 'BAAI/bge-small-en-v1.5' },
        ],
      },
      {
        workflow: 'apply_retractions', title: 'Apply retractions',
        domain: 'corpus', sub_domain: 'freshness', runs_on: 'container_apps_job',
        description:
          'Flag retracted and corrected documents so they drop out of citations without ' +
          'waiting for a rebuild.',
        params: [
          { name: 'as_of', label: 'As of date', kind: 'date', required: true },
        ],
      },
      {
        workflow: 'fit_calibration', title: 'Fit abstention calibration',
        domain: 'quality', sub_domain: 'calibration', runs_on: 'airflow',
        description:
          'Fit the confidence bias and abstention threshold on the held-out dev split. ' +
          'Never fitted on test.',
        params: [
          { name: 'dev_split', label: 'Dev split', kind: 'text', required: true, default: 'dev-400' },
        ],
      },
    ];
  }

  batches(): WorkflowBatch[] {
    const mk = (
      id: string, name: string, inst: string, stack: TechStack, status: WorkflowStatus,
      total: number, ok: number, failed: number, createdMinAgo: number, finished?: number,
    ): WorkflowBatch => ({
      wf_batch_id: id, batch_name: name, batch_instance: inst,
      domain: 'corpus', sub_domain: 'historical-ingest',
      tech_stack: stack, status,
      total_count: total, succeeded_count: ok, failed_count: failed,
      trace_id: 'trace-' + id.slice(0, 8), tenant_id: 'reference', env: 'local',
      requested_by: 'admin@local',
      created_at: this.iso(createdMinAgo),
      started_at: this.iso(createdMinAgo - 1),
      finished_at: finished !== undefined ? this.iso(finished) : undefined,
    });
    return [
      mk('b7f3a1c2-0000', 'pubmed-baseline-2026-ingest', '2026-09-12-01', 'airflow', 'RUNNING', 1334, 1102, 3, 148),
      mk('c8a4b2d3-0000', 'pubmed-delta-2026w37', '2026-09-12-03', 'airflow', 'SUCCEEDED', 96, 96, 0, 95, 41),
      mk('d9b5c3e4-0000', 'ctgov-registry-ingest', '2026-09-12-01', 'container_apps_job', 'RUNNING', 240, 118, 0, 22),
      mk('e0c6d4f5-0000', 'internal-kb-extract', '2026-09-04-02', 'airflow', 'FAILED', 64, 51, 13, 11400, 11280),
      mk('f1d7e5a6-0000', 'calibration-fit', '2026-09-11-01', 'airflow', 'SUCCEEDED', 1, 1, 0, 1500, 1494),
    ];
  }

  executions(batchId?: string): WorkflowExecution[] {
    const all: WorkflowExecution[] = [
      {
        exec_id: 'a1b2c3d4-1111', wf_batch_id: 'b7f3a1c2-0000',
        domain: 'corpus', sub_domain: 'historical-ingest', workflow: 'historical_ingest',
        tech_stack: 'airflow', wf_ref_id: 'manual__2026-09-12T06:30:00+00:00',
        status: 'RUNNING',
        input_data: { file: 'pubmed26n0912.xml.gz', records: 30_000 },
        trace_id: 'trace-b7f3a1c2', tenant_id: 'reference', env: 'local',
        requested_by: 'admin@local', created_at: this.iso(148), started_at: this.iso(147),
      },
      {
        exec_id: 'b2c3d4e5-2222', wf_batch_id: 'b7f3a1c2-0000',
        domain: 'corpus', sub_domain: 'historical-ingest', workflow: 'historical_ingest',
        tech_stack: 'airflow', wf_ref_id: 'manual__2026-09-12T06:28:00+00:00',
        status: 'SUCCEEDED',
        input_data: { file: 'pubmed26n0911.xml.gz', records: 30_000 },
        output_data: { parsed: 30_000, edges: 694_221, skipped: 0 },
        trace_id: 'trace-b7f3a1c2', tenant_id: 'reference', env: 'local',
        requested_by: 'admin@local', created_at: this.iso(150), started_at: this.iso(149),
        finished_at: this.iso(144),
      },
      {
        exec_id: 'c3d4e5f6-3333', wf_batch_id: 'b7f3a1c2-0000',
        domain: 'corpus', sub_domain: 'historical-ingest', workflow: 'historical_ingest',
        tech_stack: 'airflow', wf_ref_id: 'manual__2026-09-12T06:22:00+00:00',
        status: 'FAILED',
        input_data: { file: 'pubmed26n0907.xml.gz', records: 30_000 },
        error: {
          code: 'alignment_assert_failed',
          detail: 'major-topic count 41,208 != DB recount 41,196 for 3 descriptors',
        },
        trace_id: 'trace-b7f3a1c2', tenant_id: 'reference', env: 'local',
        requested_by: 'admin@local', created_at: this.iso(156), started_at: this.iso(155),
        finished_at: this.iso(151),
      },
      {
        // Written PENDING before the engine was called, and the engine never
        // acknowledged: the submit failure that would otherwise be invisible.
        exec_id: 'd4e5f6a7-4444', wf_batch_id: 'd9b5c3e4-0000',
        domain: 'corpus', sub_domain: 'trials', workflow: 'historical_ingest',
        tech_stack: 'container_apps_job',
        status: 'PENDING',
        input_data: { shard: 'ctgov-shard-042' },
        trace_id: 'trace-d9b5c3e4', tenant_id: 'reference', env: 'local',
        requested_by: 'admin@local', created_at: this.iso(19),
      },
      {
        exec_id: 'e5f6a7b8-5555', wf_batch_id: 'c8a4b2d3-0000',
        domain: 'corpus', sub_domain: 'freshness', workflow: 'apply_retractions',
        tech_stack: 'container_apps_job', wf_ref_id: 'caj-9f31a7',
        status: 'SUCCEEDED',
        input_data: { as_of: '2026-09-12' },
        output_data: { flagged: 214, dropped_from_citations: 214 },
        trace_id: 'trace-c8a4b2d3', tenant_id: 'reference', env: 'local',
        requested_by: 'steward@local', created_at: this.iso(95), started_at: this.iso(94),
        finished_at: this.iso(92),
      },
      {
        exec_id: 'f6a7b8c9-6666', wf_batch_id: 'f1d7e5a6-0000',
        domain: 'quality', sub_domain: 'calibration', workflow: 'fit_calibration',
        tech_stack: 'airflow', wf_ref_id: 'scheduled__2026-09-11T02:00:00+00:00',
        status: 'SUCCEEDED',
        input_data: { dev_split: 'dev-400' },
        output_data: { bias: -0.118, threshold: 0.62, auroc: 0.81 },
        trace_id: 'trace-f1d7e5a6', tenant_id: 'reference', env: 'local',
        created_at: this.iso(1500), started_at: this.iso(1499), finished_at: this.iso(1494),
      },
    ];
    return batchId ? all.filter((e) => e.wf_batch_id === batchId) : all;
  }
}
