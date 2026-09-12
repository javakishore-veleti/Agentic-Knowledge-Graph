import { Injectable, signal } from '@angular/core';
import {
  DataSet, Release, TechStack, Trace, WorkflowBatch, WorkflowDefinition, WorkflowExecution,
  WorkflowStatus,
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

  releases(): Release[] {
    // The live pin plus two candidates: one that passes every gate and one that fails
    // in the most instructive way -- a shuffled-label arm scoring above chance, which
    // means the harness itself is broken and the headline number cannot be trusted.
    const arms = (oracle: number, blind: number, maj: number, shuf: number) => [
      { arm: 'oracle' as const, accuracy: oracle, expected_min: 0.95, expected_max: 1.0 },
      { arm: 'blind' as const, accuracy: blind, expected_min: 0.30, expected_max: 0.45 },
      { arm: 'majority_class' as const, accuracy: maj, expected_min: 0.50, expected_max: 0.56 },
      { arm: 'shuffled_label' as const, accuracy: shuf, expected_min: 0.28, expected_max: 0.39 },
    ];
    const budget = (retrieval: number, grounding: number, gen: number, cal: number) => [
      { cause: 'Grounding miss', share: grounding,
        note: 'question concept never mapped; the binding constraint' },
      { cause: 'Retrieval rank', share: retrieval,
        note: 'gold document outside the read window' },
      { cause: 'Generation', share: gen, note: 'evidence admitted, answer still wrong' },
      { cause: 'Calibration', share: cal, note: 'answered when it should have abstained' },
    ];
    return [
      {
        release: 'rel-2026.09.12-02', created_at: this.iso(35), state: 'candidate',
        graph: '2026.09.12-a3f9c1', index: '2026.09.12-7b21de',
        ontology: 'mesh-2026', calibration: 'cal-2026.09.12-02',
        test_accuracy: 0.841, coverage: 0.712, leak: 0.041,
        gold_in_top_16: 0.953, unadmitted_citations: 0,
        arms: arms(0.981, 0.372, 0.533, 0.341),
        error_budget: budget(0.19, 0.52, 0.21, 0.08),
      },
      {
        release: 'rel-2026.09.12-01', created_at: this.iso(60 * 9), state: 'live',
        graph: '2026.09.12-a3f9c1', index: '2026.09.12-7b21de',
        ontology: 'mesh-2026', calibration: 'cal-2026.09.10-01',
        test_accuracy: 0.832, coverage: 0.706, leak: 0.043,
        gold_in_top_16: 0.951, unadmitted_citations: 0,
        arms: arms(0.979, 0.372, 0.533, 0.338),
        error_budget: budget(0.21, 0.50, 0.21, 0.08),
      },
      {
        release: 'rel-2026.09.11-03', created_at: this.iso(60 * 28), state: 'rejected',
        graph: '2026.09.11-c4d8e2', index: '2026.09.11-9a02bb',
        ontology: 'mesh-2026', calibration: 'cal-2026.09.11-01',
        test_accuracy: 0.869, coverage: 0.744, leak: 0.038,
        gold_in_top_16: 0.948, unadmitted_citations: 2,
        // Accuracy looks like the best of the three. It is not trustworthy: the
        // shuffled-label arm scored well above chance, so labels leaked into features.
        arms: arms(0.984, 0.371, 0.534, 0.512),
        error_budget: budget(0.24, 0.46, 0.22, 0.08),
      },
    ];
  }

  traces(): Trace[] {
    return [
      {
        answer_id: 'ans-7f3c1a92',
        question: 'Does metformin reduce cardiovascular mortality in type 2 diabetes?',
        trace_id: 'trace-8c1d9e4f7b13', tenant_id: 'reference', asked_at: this.iso(12),
        concepts: [
          { concept_id: 'D008687', name: 'Metformin', role: 'bridge', is_check_tag: false },
          { concept_id: 'D003924', name: 'Diabetes Mellitus, Type 2', role: 'bridge', is_check_tag: false },
          { concept_id: 'D002318', name: 'Cardiovascular Diseases', role: 'filter', is_check_tag: false },
          { concept_id: 'D006801', name: 'Humans', role: 'ignore', is_check_tag: true },
        ],
        candidates: [
          { doc_id: '12345678', title: 'Metformin and cardiovascular outcomes in type 2 diabetes',
            dense_score: 0.812, rerank_score: 0.941, route: 'co_annotation',
            reason: 'directly about both bridge concepts', path: ['12345678'],
            retracted: false, quotable: true, admitted: true, cited: true },
          { doc_id: '23456789', title: 'Biguanides and macrovascular risk: a pooled analysis',
            dense_score: 0.774, rerank_score: 0.882, route: 'ontology_ancestry',
            reason: 'Biguanides is an ancestor of Metformin',
            path: ['23456789', 'D008687'], retracted: false, quotable: true,
            admitted: true, cited: true },
          { doc_id: '34567890', title: 'Glycaemic control and mortality: cohort review',
            dense_score: 0.731, rerank_score: 0.640, route: 'citation_adjacency',
            reason: 'cited by a document about Metformin',
            path: ['34567890', '12345678'], retracted: false, quotable: true,
            admitted: true, cited: false },
          { doc_id: '45678901', title: 'Retracted: metformin cardioprotection in mice',
            dense_score: 0.706, route: 'co_annotation',
            reason: 'shares both bridge concepts', path: ['45678901'],
            // Retained as a candidate and annotated, not silently dropped: certification
            // annotates. It is excluded from the admitted set by the retraction rule.
            retracted: true, quotable: true, admitted: false, cited: false },
        ],
        gates: [
          { gate: 'entry point', passed: true, detail: '2 bridge concepts grounded' },
          { gate: 'concept count', passed: true, detail: '3 specific concepts after check tags removed' },
          { gate: 'path exists', passed: true, detail: 'co-annotation route on top candidate' },
          { gate: 'quotable', passed: true, detail: 'abstract present on 3 of 4 candidates' },
          { gate: 'not only retracted', passed: true, detail: '1 retracted candidate excluded' },
          { gate: 'evidence as of date', passed: true, detail: 'no as-of constraint' },
        ],
        posterior: { yes: 0.8402, no: 0.1203, maybe: 0.0395 },
        raw_confidence: 0.8402, calibrated_confidence: 0.7221, threshold: 0.62,
        disposition: 'ANSWER',
        answer_text:
          'Metformin was associated with lower cardiovascular mortality in type 2 diabetes ' +
          '[12345678], with pooled analyses of biguanides showing a consistent direction of ' +
          'effect [23456789].',
        pins: { graph: '2026.09.12-a3f9c1', index: '2026.09.12-7b21de',
                ontology: 'mesh-2026', calibration: 'cal-2026.09.10-01' },
      },
      {
        answer_id: 'ans-4b02de51',
        question: 'What is the optimal dose of compound XJ-9921 for hepatic clearance?',
        trace_id: 'trace-1a4b7c2d9e05', tenant_id: 'reference', asked_at: this.iso(48),
        concepts: [
          { concept_id: 'D005355', name: 'Liver', role: 'filter', is_check_tag: false },
          { concept_id: 'D006801', name: 'Humans', role: 'ignore', is_check_tag: true },
        ],
        candidates: [],
        gates: [
          // Fails at the first gate, so no generator call was made and nothing was spent.
          { gate: 'entry point', passed: false,
            detail: '"XJ-9921" matched no known concept; only a filter concept remained' },
          { gate: 'concept count', passed: false, detail: '0 bridge concepts' },
          { gate: 'path exists', passed: false, detail: 'not evaluated' },
          { gate: 'quotable', passed: false, detail: 'not evaluated' },
          { gate: 'not only retracted', passed: false, detail: 'not evaluated' },
          { gate: 'evidence as of date', passed: false, detail: 'not evaluated' },
        ],
        threshold: 0.62,
        disposition: 'REFUSE', refusal_reason: 'no_entry_point',
        pins: { graph: '2026.09.12-a3f9c1', index: '2026.09.12-7b21de',
                ontology: 'mesh-2026', calibration: 'cal-2026.09.10-01' },
      },
      {
        answer_id: 'ans-9d71fa30',
        question: 'Is aspirin effective for primary prevention of stroke?',
        as_of: '2015-01-01',
        trace_id: 'trace-33e9a1b0c7f2', tenant_id: 'reference', asked_at: this.iso(120),
        concepts: [
          { concept_id: 'D001241', name: 'Aspirin', role: 'bridge', is_check_tag: false },
          { concept_id: 'D020521', name: 'Stroke', role: 'bridge', is_check_tag: false },
        ],
        candidates: [
          { doc_id: '56789012', title: 'Aspirin in primary prevention: 2019 meta-analysis',
            dense_score: 0.864, rerank_score: 0.912, route: 'co_annotation',
            reason: 'shares both bridge concepts',
            path: ['56789012'], retracted: false, quotable: true,
            // Published after the as-of date, so excluded from evidence and citations.
            admitted: false, cited: false },
        ],
        gates: [
          { gate: 'entry point', passed: true, detail: '2 bridge concepts grounded' },
          { gate: 'concept count', passed: true, detail: '2 specific concepts' },
          { gate: 'path exists', passed: true, detail: 'co-annotation route found' },
          { gate: 'quotable', passed: true, detail: 'abstract present' },
          { gate: 'not only retracted', passed: true, detail: 'no retracted candidates' },
          { gate: 'evidence as of date', passed: false,
            detail: 'every candidate published after 2015-01-01' },
        ],
        threshold: 0.62,
        disposition: 'REFUSE', refusal_reason: 'no_evidence_as_of_date',
        pins: { graph: '2026.09.12-a3f9c1', index: '2026.09.12-7b21de',
                ontology: 'mesh-2026', calibration: 'cal-2026.09.10-01' },
      },
    ];
  }
}
