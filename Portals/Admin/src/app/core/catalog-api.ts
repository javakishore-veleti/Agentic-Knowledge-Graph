import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, InjectionToken, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import {
  AppEndpointDto, ConnectionType, CreateMioReq, InitialDataEntity, DataInstanceDto, DatasetEndpointDto, DataInstanceExecDto, DataInstancesResp,
  DatasetDto, DomainDto, InvokeResp, MioDto, MioLineageResp, MioWorkflowDto, Paged,
  InitialDataStatusDto, LoadResultDto, Provider, UpdateMioReq, WorkflowDto,
} from './catalog-models';

/** What the portal needs from the DataCatalog service.
 *
 * Two implementations: HTTP against the real API, and a mock for working on the UI
 * without the stack up. Components depend on this token and never on either class. */
export abstract class CatalogApi {
  abstract domains(opts?: { cursor?: string; limit?: number; q?: string }): Observable<Paged<DomainDto>>;
  abstract datasets(filters?: { domain?: string; adapter?: string; q?: string; cursor?: string; limit?: number }): Observable<Paged<DatasetDto>>;
  abstract mios(filters?: { domain?: string; state?: string; tech_stack?: string; has_cdc?: boolean; q?: string; cursor?: string; limit?: number }): Observable<Paged<MioDto>>;
  abstract instances(mioId: string): Observable<DataInstancesResp>;
  abstract execs(instanceId: string): Observable<Paged<DataInstanceExecDto>>;
  abstract endpoints(filters?: { provider?: string; env?: string }): Observable<Paged<AppEndpointDto>>;
  abstract lineage(mioId: string): Observable<MioLineageResp>;
  abstract datasetLocations(datasetId: string): Observable<{ dataset_id: string; items: DatasetEndpointDto[] }>;
  abstract initialDataStatus(): Observable<{ items: InitialDataStatusDto[] }>;
  abstract loadInitialData(entity: string, force: boolean): Observable<LoadResultDto>;

  abstract workflows(filters?: { domain?: string; q?: string }): Observable<Paged<WorkflowDto>>;
  abstract mioWorkflows(mioId: string): Observable<{ mio_id: string; items: MioWorkflowDto[] }>;
  abstract attachWorkflow(mioId: string, workflowId: string, purpose: string): Observable<unknown>;
  abstract detachWorkflow(mioId: string, workflowId: string): Observable<unknown>;
  abstract invokeWorkflow(mioId: string, workflowId: string, input: Record<string, unknown>): Observable<InvokeResp>;
  abstract createMio(req: CreateMioReq): Observable<{ mio: MioDto }>;
  abstract updateMio(req: UpdateMioReq): Observable<{ mio: MioDto }>;
  abstract deleteMio(mioId: string): Observable<{ deleted: boolean }>;
  /** Whether the real service is reachable. Drives the banner rather than a silent fallback. */
  abstract live(): Observable<boolean>;
}

export const CATALOG_BASE_URL = new InjectionToken<string>('CATALOG_BASE_URL');

@Injectable()
export class HttpCatalogApi extends CatalogApi {
  private readonly http = inject(HttpClient);
  private readonly base = inject(CATALOG_BASE_URL);

  private params(o: Record<string, string | number | boolean | undefined> = {}): HttpParams {
    let p = new HttpParams();
    for (const [k, v] of Object.entries(o)) {
      if (v !== undefined && v !== '') p = p.set(k, String(v));
    }
    return p;
  }

  domains(o: { cursor?: string; limit?: number; q?: string } = {}): Observable<Paged<DomainDto>> {
    return this.http.get<Paged<DomainDto>>(`${this.base}/api/v1/domains`, { params: this.params(o) });
  }

  datasets(f: { domain?: string; adapter?: string; q?: string; cursor?: string; limit?: number } = {}): Observable<Paged<DatasetDto>> {
    return this.http.get<Paged<DatasetDto>>(`${this.base}/api/v1/datasets`, { params: this.params(f) });
  }

  mios(f: { domain?: string; state?: string; tech_stack?: string; has_cdc?: boolean; q?: string; cursor?: string; limit?: number } = {}): Observable<Paged<MioDto>> {
    return this.http.get<Paged<MioDto>>(`${this.base}/api/v1/mios`, { params: this.params(f) });
  }

  instances(mioId: string): Observable<DataInstancesResp> {
    return this.http.get<DataInstancesResp>(`${this.base}/api/v1/mios/${mioId}/instances`);
  }

  execs(instanceId: string): Observable<Paged<DataInstanceExecDto>> {
    return this.http.get<Paged<DataInstanceExecDto>>(`${this.base}/api/v1/instances/${instanceId}/execs`);
  }

  endpoints(f: { provider?: string; env?: string } = {}): Observable<Paged<AppEndpointDto>> {
    return this.http.get<Paged<AppEndpointDto>>(`${this.base}/api/v1/app-endpoints`, { params: this.params(f) });
  }

  lineage(mioId: string): Observable<MioLineageResp> {
    return this.http.get<MioLineageResp>(`${this.base}/api/v1/mios/${mioId}/lineage`);
  }

  datasetLocations(datasetId: string): Observable<{ dataset_id: string; items: DatasetEndpointDto[] }> {
    return this.http.get<{ dataset_id: string; items: DatasetEndpointDto[] }>(
      `${this.base}/api/v1/datasets/${datasetId}/endpoints`);
  }

  initialDataStatus(): Observable<{ items: InitialDataStatusDto[] }> {
    return this.http.get<{ items: InitialDataStatusDto[] }>(
      `${this.base}/api/v1/admin/initial-data`);
  }

  loadInitialData(entity: string, force: boolean): Observable<LoadResultDto> {
    return this.http.post<LoadResultDto>(
      `${this.base}/api/v1/admin/initial-data/${entity}/load`, { force });
  }

  workflows(f: { domain?: string; q?: string } = {}): Observable<Paged<WorkflowDto>> {
    return this.http.get<Paged<WorkflowDto>>(`${this.base}/api/v1/workflows`, { params: this.params(f) });
  }

  mioWorkflows(mioId: string): Observable<{ mio_id: string; items: MioWorkflowDto[] }> {
    return this.http.get<{ mio_id: string; items: MioWorkflowDto[] }>(
      `${this.base}/api/v1/mios/${mioId}/workflows`);
  }

  attachWorkflow(mioId: string, workflowId: string, purpose: string): Observable<unknown> {
    return this.http.post(`${this.base}/api/v1/mios/${mioId}/workflows`,
      { mio_id: mioId, workflow_id: workflowId, purpose });
  }

  detachWorkflow(mioId: string, workflowId: string): Observable<unknown> {
    return this.http.delete(`${this.base}/api/v1/mios/${mioId}/workflows/${workflowId}`);
  }

  invokeWorkflow(mioId: string, workflowId: string, input: Record<string, unknown>): Observable<InvokeResp> {
    return this.http.post<InvokeResp>(
      `${this.base}/api/v1/mios/${mioId}/workflows/${workflowId}/invoke`,
      { mio_id: mioId, workflow_id: workflowId, input_data: input });
  }

  createMio(req: CreateMioReq): Observable<{ mio: MioDto }> {
    return this.http.post<{ mio: MioDto }>(`${this.base}/api/v1/mios`, req);
  }

  updateMio(req: UpdateMioReq): Observable<{ mio: MioDto }> {
    return this.http.patch<{ mio: MioDto }>(`${this.base}/api/v1/mios/${req.mio_id}`, req);
  }

  deleteMio(mioId: string): Observable<{ deleted: boolean }> {
    return this.http.delete<{ deleted: boolean }>(`${this.base}/api/v1/mios/${mioId}`);
  }

  live(): Observable<boolean> {
    return new Observable<boolean>((sub) => {
      this.http.get<{ status: string }>(`${this.base}/health`).subscribe({
        next: (h) => { sub.next(h.status === 'ok'); sub.complete(); },
        error: () => { sub.next(false); sub.complete(); },
      });
    });
  }
}

/** Mock data shaped exactly like the API's responses, so swapping to HTTP changes
 *  nothing in a component. Used when the middleware stack is not running. */
@Injectable()
export class MockCatalogApi extends CatalogApi {
  readonly isMock = signal(true);

  /** Mutable so create/update/delete are visible in the UI without a backend. The real
   *  implementation holds no such state -- this exists only to make the portal usable
   *  when the middleware stack is not running. */
  private mios_: MioDto[] | null = null;
  private mioWorkflows_ = new Map<string, MioWorkflowDto[]>();

  private page<T>(items: T[]): Paged<T> {
    return { page: { total: items.length, limit: 50, next_cursor: null }, items };
  }

  private iso(minutesAgo: number): string {
    return new Date(Date.now() - minutesAgo * 60_000).toISOString();
  }

  domains(): Observable<Paged<DomainDto>> {
    return of(this.page<DomainDto>([
      { domain_id: 'd1', code: 'biomedical', name: 'Biomedical',
        description: 'Literature and trials', created_at: this.iso(60 * 300) },
      { domain_id: 'd2', code: 'enterprise', name: 'Enterprise',
        description: 'Internal documentation', created_at: this.iso(60 * 200) },
    ]));
  }

  datasets(f: { domain?: string; adapter?: string; q?: string; cursor?: string; limit?: number } = {}): Observable<Paged<DatasetDto>> {
    const all: DatasetDto[] = [
      { dataset_id: 'ds1', domain_id: 'd1', code: 'pubmed', name: 'PubMed baseline',
        description: 'Annual baseline, edges shipped by the publisher',
        source_version: 'pubmed-baseline-2026', adapter: 'pubmed',
        sub_domain: 'literature', created_at: this.iso(60 * 26) },
      { dataset_id: 'ds2', domain_id: 'd1', code: 'pubmed', name: 'PubMed baseline',
        description: 'Weekly delta', source_version: 'pubmed-delta-2026w37',
        adapter: 'pubmed', sub_domain: 'literature', created_at: this.iso(95) },
      { dataset_id: 'ds3', domain_id: 'd1', code: 'ctgov', name: 'ClinicalTrials registry',
        description: 'No shipped edges; extraction adapter required',
        source_version: 'ctgov-2026-09', adapter: 'generic-extraction',
        sub_domain: 'trials', created_at: this.iso(22) },
      { dataset_id: 'ds4', domain_id: 'd2', code: 'kb', name: 'Engineering KB',
        description: 'Internal documentation', source_version: 'kb-2026-09-04',
        adapter: 'generic-extraction', sub_domain: 'documentation',
        created_at: this.iso(60 * 190) },
    ];
    const domains: Record<string, string> = { d1: 'biomedical', d2: 'enterprise' };
    return of(this.page(all.filter((d) =>
      (!f.domain || domains[d.domain_id] === f.domain) &&
      (!f.adapter || d.adapter === f.adapter) &&
      (!f.q || (d.name + d.code + d.source_version).toLowerCase().includes(f.q.toLowerCase())))));
  }

  private seedMios(): MioDto[] {
    if (this.mios_) return this.mios_;
    this.mios_ = [
      { mio_id: 'm1', domain_id: 'd1', domain_code: 'biomedical', code: 'pubmed-csr-graph',
        name: 'PubMed CSR graph', tech_stack: 'csr_graph', state: 'live',
        pinned_version: '2026.09.12-a3f9c1', documents_count: 39_990_112,
        edges_count: 929_824_202, size_bytes: 442_000_000_000,
        validations: { alignment_assert: true, source_recount: true },
        validations_pass: true, dataset_count: 1, workflow_count: 2, instance_count: 3,
        has_cdc: true, generated_mio_count: 1, last_exec_at: this.iso(148),
        created_at: this.iso(60 * 300), updated_at: this.iso(148) },
      { mio_id: 'm2', domain_id: 'd1', domain_code: 'biomedical', code: 'pubmed-vector-index',
        name: 'PubMed vector index', tech_stack: 'pgvector', state: 'live',
        pinned_version: '2026.09.12-7b21de', documents_count: 28_300_441,
        edges_count: 0, size_bytes: 96_000_000_000,
        validations: { uniqueness_assert: true, count_audit: true },
        validations_pass: true, dataset_count: 1, workflow_count: 1, instance_count: 1,
        has_cdc: false, generated_mio_count: 0, last_exec_at: this.iso(150),
        created_at: this.iso(60 * 280), updated_at: this.iso(150) },
      { mio_id: 'm3', domain_id: 'd1', domain_code: 'biomedical', code: 'ctgov-index',
        name: 'Trials index', tech_stack: 'opensearch', state: 'building',
        pinned_version: null, documents_count: 512_884, edges_count: 0,
        size_bytes: 7_300_000_000,
        // Nothing checked yet. An empty validations object is not a pass.
        validations: {}, validations_pass: false, dataset_count: 1, workflow_count: 1,
        instance_count: 1, has_cdc: false, generated_mio_count: 0,
        last_exec_at: this.iso(22), created_at: this.iso(60 * 3), updated_at: this.iso(22) },
      { mio_id: 'm4', domain_id: 'd2', domain_code: 'enterprise', code: 'kb-graph',
        name: 'KB extracted graph', tech_stack: 'csr_graph', state: 'rejected',
        pinned_version: null, documents_count: 18_402, edges_count: 41_339,
        size_bytes: 980_000_000,
        // The recount disagreed with the CSR count: not promotable.
        validations: { alignment_assert: true, source_recount: false },
        validations_pass: false, dataset_count: 1, workflow_count: 1, instance_count: 1,
        has_cdc: false, generated_mio_count: 0, last_exec_at: this.iso(11_280),
        created_at: this.iso(60 * 200), updated_at: this.iso(11_280) },
    ];
    return this.mios_;
  }

  mios(f: { domain?: string; state?: string; tech_stack?: string; has_cdc?: boolean; q?: string; cursor?: string; limit?: number } = {}): Observable<Paged<MioDto>> {
    const all = this.seedMios();
    return of(this.page(all.filter((m) =>
      (!f.domain || m.domain_code === f.domain) &&
      (!f.state || m.state === f.state) &&
      (!f.tech_stack || m.tech_stack === f.tech_stack) &&
      (f.has_cdc === undefined || m.has_cdc === f.has_cdc) &&
      (!f.q || (m.name + m.code).toLowerCase().includes(f.q.toLowerCase())))));
  }

  /** Persisted so the Administration screen behaves like the real thing without a
   *  backend: loading an entity fills it, a second press reports already_loaded, and the
   *  result survives a refresh.
   *
   *  It lives in localStorage because an in-memory Map made a completed load vanish on
   *  reload, which reads as the load having failed. The real implementation persists in
   *  catalog.initial_data_tracker; this only has to be convincing enough not to mislead.
   *  Wrapped in try/catch: storage throws in private windows and is simply absent in
   *  some embedded views. */
  private static readonly LOADED_KEY = 'akg.mock.initialData';

  private readLoaded(): Record<string, { count: number; at: string }> {
    try {
      return JSON.parse(localStorage.getItem(MockCatalogApi.LOADED_KEY) ?? '{}');
    } catch {
      return {};
    }
  }

  private writeLoaded(state: Record<string, { count: number; at: string }>): void {
    try {
      localStorage.setItem(MockCatalogApi.LOADED_KEY, JSON.stringify(state));
    } catch {
      // Nothing to do: the screen still works, it just forgets on reload.
    }
  }

  initialDataStatus(): Observable<{ items: InitialDataStatusDto[] }> {
    const spec: [InitialDataEntity, number, InitialDataEntity | null, number][] = [
      ['purposes', 1, null, 13],
      ['domains', 2, null, 2],
      ['endpoints', 3, null, 2],
      ['datasets', 4, 'domains', 4],
      ['workflows', 5, 'purposes', 5],
    ];
    return of({
      items: spec.map(([entity, order, depends, seedCount]) => {
        const done = this.readLoaded()[entity];
        return {
          entity, load_order: order, depends_on: depends,
          row_count: done ? done.count : (entity === 'endpoints' ? 2 : 0),
          last_status: done ? ('SUCCEEDED' as const) : null,
          last_inserted: done ? done.count : null,
          last_skipped: 0,
          last_run_at: done ? done.at : null,
        };
      }),
    });
  }

  loadInitialData(entity: string, force: boolean): Observable<LoadResultDto> {
    const counts: Record<string, number> = {
      purposes: 13, domains: 2, endpoints: 2, datasets: 4, workflows: 5,
    };
    const deps: Record<string, string | undefined> = {
      datasets: 'domains', workflows: 'purposes',
    };
    const state = this.readLoaded();
    const need = deps[entity];
    if (need && !state[need]) {
      return of({ entity: entity as InitialDataEntity, claimed: false,
                  reason: `requires_${need}` });
    }
    if (state[entity] && !force) {
      return of({ entity: entity as InitialDataEntity, claimed: false,
                  reason: 'already_loaded' });
    }
    state[entity] = { count: counts[entity] ?? 0, at: new Date().toISOString() };
    this.writeLoaded(state);
    return of({ entity: entity as InitialDataEntity, claimed: true, reason: 'claimed',
                tracker_id: crypto.randomUUID() });
  }

  datasetLocations(datasetId: string): Observable<{ dataset_id: string; items: DatasetEndpointDto[] }> {
    const mk = (
      id: string, role: DatasetEndpointDto['role'], kind: string, uri: string,
      state: DatasetEndpointDto['state'], bytes: number, appId: string | null,
      primary = false,
    ): DatasetEndpointDto => ({
      dataset_endpoint_id: id, dataset_id: datasetId, role, app_endpoint_id: appId,
      location_kind: kind, uri, options: {}, format: null, bytes, object_count: 0,
      state, is_primary: primary, last_synced_at: null,
    });
    const byDataset: Record<string, DatasetEndpointDto[]> = {
      ds1: [
        mk('de1', 'source', 'ftp', 'ftp://ftp.ncbi.nlm.nih.gov/pubmed/baseline/', 'declared', 0, null, true),
        mk('de2', 'landing', 's3', 's3://akg-raw/pubmed/2026/', 'available', 442_000_000_000, 'a1', true),
        mk('de3', 'curated', 'local_fs', 'file:///mnt/data/parquet/pubmed/', 'available', 96_000_000_000, 'a0'),
      ],
      ds2: [
        mk('de4', 'source', 'ftp', 'ftp://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/', 'declared', 0, null, true),
        mk('de5', 'landing', 'azure_blob', 'abfss://raw@akgraw/pubmed/w37/', 'syncing', 0, 'a4', true),
      ],
      ds3: [
        mk('de6', 'source', 'http_url', 'https://clinicaltrials.gov/api/v2/studies', 'declared', 0, null, true),
        // Nothing landed yet: acquiring is the action the drawer offers.
        mk('de7', 'landing', 's3', 's3://akg-raw/ctgov/2026-09/', 'declared', 0, 'a1', true),
      ],
      ds4: [
        mk('de8', 'source', 'file_server', 'smb://files.internal/kb/', 'declared', 0, null, true),
        // Acquisition ran and failed: retry is allowed without forcing.
        mk('de9', 'landing', 'local_fs', 'file:///mnt/data/raw/kb/', 'failed', 0, 'a0', true),
      ],
    };
    return of({ dataset_id: datasetId, items: byDataset[datasetId] ?? [] });
  }

  workflows(f: { domain?: string; q?: string } = {}): Observable<Paged<WorkflowDto>> {
    const all: WorkflowDto[] = [
      { workflow_id: 'w1', code: 'historical_ingest', name: 'Historical corpus ingest',
        description: 'Acquire, parse, link the ontology, build the CSR graph, embed, ' +
          'consolidate, and emit a manifest. Fans out one execution per source file.',
        domain: 'corpus', sub_domain: 'historical-ingest', default_tech_stack: 'airflow',
        purpose: 'build', is_active: true, params_json: [
          { name: 'source_version', label: 'Source version', kind: 'text', required: true,
            default: 'pubmed-baseline-2026' },
          { name: 'adapter', label: 'Adapter', kind: 'select', required: true,
            options: ['pubmed', 'generic-extraction'], default: 'pubmed',
            help: 'Edge-bearing sources parse directly; generic extraction reports cost separately.' },
          { name: 'smoke', label: 'Smoke run', kind: 'bool', required: false, default: true,
            help: 'Shrinks to 12 files. Use before spending GPU time.' },
        ] },
      { workflow_id: 'w2', code: 'rebuild_index', name: 'Rebuild vector index',
        description: 'Re-embed and consolidate shards into one pinnable index.',
        domain: 'corpus', sub_domain: 'index', default_tech_stack: 'airflow',
        purpose: 'build', is_active: true, params_json: [
          { name: 'model', label: 'Embedding model', kind: 'select', required: true,
            options: ['BAAI/bge-small-en-v1.5', 'BAAI/bge-base-en-v1.5'],
            default: 'BAAI/bge-small-en-v1.5' },
        ] },
      { workflow_id: 'w3', code: 'apply_retractions', name: 'Apply retractions',
        description: 'Flag retracted and corrected documents so they drop out of ' +
          'citations without waiting for a rebuild.',
        domain: 'corpus', sub_domain: 'freshness', default_tech_stack: 'container_apps_job',
        purpose: 'retract', is_active: true, params_json: [
          { name: 'as_of', label: 'As of date', kind: 'date', required: true },
        ] },
      { workflow_id: 'w4', code: 'fit_calibration', name: 'Fit abstention calibration',
        description: 'Fit the confidence bias and abstention threshold on the held-out ' +
          'dev split. Never fitted on test.',
        domain: 'quality', sub_domain: 'calibration', default_tech_stack: 'airflow',
        purpose: 'calibrate', is_active: true, params_json: [
          { name: 'dev_split', label: 'Dev split', kind: 'text', required: true, default: 'dev-400' },
        ] },
      { workflow_id: 'w5', code: 'legacy_export', name: 'Legacy export',
        description: 'Retired. Kept to show that a deactivated workflow cannot be attached.',
        domain: 'corpus', sub_domain: 'export', default_tech_stack: 'airflow',
        purpose: 'build', is_active: false, params_json: [] },
    ];
    return of(this.page(all.filter((w) =>
      (!f.domain || w.domain === f.domain) &&
      (!f.q || (w.name + w.code).toLowerCase().includes(f.q.toLowerCase())))));
  }

  mioWorkflows(mioId: string): Observable<{ mio_id: string; items: MioWorkflowDto[] }> {
    if (!this.mioWorkflows_.has(mioId)) {
      const seed: Record<string, string[]> = { m1: ['w1', 'w3'], m2: ['w2'], m3: ['w1'], m4: ['w1'] };
      const codes = seed[mioId] ?? [];
      let masters: WorkflowDto[] = [];
      this.workflows().subscribe((p) => (masters = p.items));
      this.mioWorkflows_.set(mioId, masters
        .filter((w) => codes.includes(w.workflow_id))
        .map((w) => ({
          workflow_id: w.workflow_id, workflow_code: w.code, workflow_name: w.name,
          description: w.description, default_tech_stack: w.default_tech_stack,
          purpose: w.purpose, enabled: true, params_json: w.params_json,
          param_overrides_json: {}, workflow_active: w.is_active,
        })));
    }
    return of({ mio_id: mioId, items: this.mioWorkflows_.get(mioId) ?? [] });
  }

  attachWorkflow(mioId: string, workflowId: string, purpose: string): Observable<unknown> {
    let master: WorkflowDto | undefined;
    this.workflows().subscribe((p) => (master = p.items.find((w) => w.workflow_id === workflowId)));
    if (!master) return of({ attached: false });
    if (!master.is_active) {
      // Mirrors the service: attaching a deactivated workflow would put a trigger button
      // in the portal that cannot work.
      return of({ attached: false, detail: `workflow ${master.code} is not active` });
    }
    const list = this.mioWorkflows_.get(mioId) ?? [];
    if (!list.some((w) => w.workflow_id === workflowId)) {
      list.push({
        workflow_id: master.workflow_id, workflow_code: master.code,
        workflow_name: master.name, description: master.description,
        default_tech_stack: master.default_tech_stack, purpose, enabled: true,
        params_json: master.params_json, param_overrides_json: {}, workflow_active: true,
      });
    }
    this.mioWorkflows_.set(mioId, list);
    this.bumpWorkflowCount(mioId, +1);
    return of({ attached: true });
  }

  detachWorkflow(mioId: string, workflowId: string): Observable<unknown> {
    const list = (this.mioWorkflows_.get(mioId) ?? []).filter((w) => w.workflow_id !== workflowId);
    this.mioWorkflows_.set(mioId, list);
    this.bumpWorkflowCount(mioId, -1);
    return of({ detached: true });
  }

  private bumpWorkflowCount(mioId: string, delta: number): void {
    const m = this.seedMios().find((x) => x.mio_id === mioId);
    if (m) m.workflow_count = Math.max(0, m.workflow_count + delta);
  }

  invokeWorkflow(mioId: string, workflowId: string, input: Record<string, unknown>): Observable<InvokeResp> {
    return of({
      mio_id: mioId, workflow_id: workflowId,
      data_instance_exec_id: crypto.randomUUID(),
      // PENDING until an engine acknowledges: the same contract as the service.
      status: 'PENDING', wf_ref_id: null,
    });
  }

  createMio(req: CreateMioReq): Observable<{ mio: MioDto }> {
    const now = new Date().toISOString();
    const mio: MioDto = {
      mio_id: crypto.randomUUID(), domain_id: 'd1', domain_code: req.domain_code,
      code: req.code, name: req.name, tech_stack: req.tech_stack,
      state: 'draft', pinned_version: null, documents_count: 0, edges_count: 0,
      size_bytes: 0,
      // Nothing has checked it, and "nothing checked" is not a pass.
      validations: {}, validations_pass: false,
      dataset_count: req.dataset_ids?.length ?? 0, workflow_count: 0, instance_count: 0,
      has_cdc: false, generated_mio_count: 0, last_exec_at: null,
      created_at: now, updated_at: now,
    };
    this.seedMios().unshift(mio);
    return of({ mio });
  }

  updateMio(req: UpdateMioReq): Observable<{ mio: MioDto }> {
    const m = this.seedMios().find((x) => x.mio_id === req.mio_id);
    if (!m) return of({ mio: this.seedMios()[0] });
    if (req.name !== undefined) m.name = req.name;
    if (req.tech_stack !== undefined) m.tech_stack = req.tech_stack;
    if (req.pinned_version !== undefined) m.pinned_version = req.pinned_version;
    if (req.state !== undefined) m.state = req.state;
    m.updated_at = new Date().toISOString();
    return of({ mio: m });
  }

  deleteMio(mioId: string): Observable<{ deleted: boolean }> {
    const all = this.seedMios();
    const i = all.findIndex((x) => x.mio_id === mioId);
    if (i >= 0) all.splice(i, 1);
    return of({ deleted: i >= 0 });
  }

  instances(mioId: string): Observable<DataInstancesResp> {
    const byMio: Record<string, DataInstanceDto[]> = {
      m1: [
        { data_instance_id: 'i1', mio_id: 'm1', kind: 'cdc', label: 'pubmed cdc stream',
          description: 'Continuous change capture', state: 'active',
          stream_cursor: 'lsn-0/1A2B3C', created_at: this.iso(60 * 40), updated_at: this.iso(2) },
        { data_instance_id: 'i2', mio_id: 'm1', kind: 'historical', label: 'baseline 2026',
          description: '1,334 files', state: 'completed', stream_cursor: null,
          created_at: this.iso(60 * 26), updated_at: this.iso(60 * 24) },
        { data_instance_id: 'i3', mio_id: 'm1', kind: 'realtime', label: 'daily delta',
          description: 'Kafka consumer', state: 'active', stream_cursor: null,
          created_at: this.iso(95), updated_at: this.iso(3) },
      ],
      m2: [
        { data_instance_id: 'i4', mio_id: 'm2', kind: 'historical', label: 'embed 28.3M',
          description: 'bge-small', state: 'completed', stream_cursor: null,
          created_at: this.iso(60 * 20), updated_at: this.iso(150) },
      ],
      m3: [
        { data_instance_id: 'i5', mio_id: 'm3', kind: 'historical', label: 'ctgov load',
          description: '', state: 'active', stream_cursor: null,
          created_at: this.iso(22), updated_at: this.iso(1) },
      ],
      m4: [
        { data_instance_id: 'i6', mio_id: 'm4', kind: 'historical', label: 'kb extract',
          description: '', state: 'failed', stream_cursor: null,
          created_at: this.iso(11_400), updated_at: this.iso(11_280) },
      ],
    };
    const items = byMio[mioId] ?? [];
    return of({
      page: { total: items.length, limit: 50, next_cursor: null },
      items,
      cdc_instance_id: items.find((i) => i.kind === 'cdc')?.data_instance_id ?? null,
    });
  }

  execs(instanceId: string): Observable<Paged<DataInstanceExecDto>> {
    const mk = (id: string, status: string, minsAgo: number, out: unknown[]): DataInstanceExecDto => ({
      data_instance_exec_id: id, data_instance_id: instanceId, status,
      input_tech: 'blob', output_tech: 'csr_graph',
      input_data_json: [{ dataset_id: 'ds1', location: 'blob://raw/pubmed', rows: 30_000 }],
      output_data_json: out, wf_execs_json: [{ workflow: 'historical_ingest', status }],
      produced_mio_id: null, trace_id: 'trace-' + id, env: 'local',
      requested_by: 'admin@local', created_at: this.iso(minsAgo),
      started_at: this.iso(minsAgo - 1),
      finished_at: status === 'RUNNING' ? null : this.iso(minsAgo - 6),
    });
    return of(this.page([
      mk('e1', 'SUCCEEDED', 150, [{ location: 'blob://graph/2026.09.12-a3f9c1', tech_stack: 'csr_graph' }]),
      mk('e2', 'RUNNING', 20, []),
    ]));
  }

  endpoints(f: { provider?: string; env?: string } = {}): Observable<Paged<AppEndpointDto>> {
    // The eleven system endpoints, in the provider shape of migration 011. One row per
    // WAY of reaching a service, because the way is what differs: the same bucket is
    // reached by a profile on a laptop, an attached role in EKS, and keys in CI.
    const mk = (
      id: string, code: string, name: string, description: string,
      provider: Provider, service: string, ctype: ConnectionType,
      details: Record<string, unknown>, env: string,
    ): AppEndpointDto => ({
      app_endpoint_id: id, code, name, description, provider,
      provider_service: service, connection_type: ctype, connection_details: details,
      env, is_active: true, is_system: true,
    });

    const all: AppEndpointDto[] = [
      mk('a0', 'local-fs', 'Local filesystem', 'Files on the machine running the code',
         'local', 'filesystem', 'anonymous',
         { env: { root: 'AKG_LOCAL_DATA_ROOT' } }, 'local'),

      mk('a1', 'pg-local', 'PostgreSQL (local)', 'Postgres in the local Docker stack',
         'local', 'postgres', 'env_vars',
         { host: 'localhost', port: 5432, database: 'akg', username: 'akg',
           sslmode: 'disable',
           env: { host: 'AKG_PG_HOST', port: 'AKG_PG_PORT', database: 'AKG_PG_DATABASE',
                  username: 'AKG_PG_USERNAME', password: 'AKG_PG_PASSWORD' } }, 'local'),

      mk('a2', 'pg-aws-rds', 'PostgreSQL (AWS RDS)', 'Amazon RDS for PostgreSQL',
         'aws', 'rds_postgres', 'env_vars',
         { host: 'CHANGE-ME.rds.amazonaws.com', port: 5432, database: 'akg',
           username: 'akg', sslmode: 'require',
           env: { host: 'AKG_RDS_PG_HOST', password: 'AKG_RDS_PG_PASSWORD' } }, 'aws-dev'),

      mk('a3', 'pg-azure', 'PostgreSQL (Azure Flexible Server)',
         'Azure Database for PostgreSQL', 'azure', 'postgres_flexible_server', 'env_vars',
         { host: 'CHANGE-ME.postgres.database.azure.com', port: 5432, database: 'akg',
           username: 'akg', sslmode: 'require',
           env: { host: 'AKG_AZURE_PG_HOST', password: 'AKG_AZURE_PG_PASSWORD' } },
         'azure-dev'),

      mk('a4', 'aws-s3-profile', 'AWS S3 (named profile)',
         'Uses a profile from ~/.aws/credentials on this machine', 'aws', 's3', 'profile',
         { profile: 'default',
           env: { bucket: 'AKG_AWS_S3_BUCKET', region: 'AKG_AWS_REGION' } }, 'local'),

      mk('a5', 'aws-s3-keys', 'AWS S3 (access keys)',
         'Access key and secret supplied by the environment', 'aws', 's3', 'env_vars',
         { env: { bucket: 'AKG_AWS_S3_BUCKET', region: 'AKG_AWS_REGION',
                  access_key_id: 'AKG_AWS_ACCESS_KEY_ID',
                  secret_access_key: 'AKG_AWS_SECRET_ACCESS_KEY' } }, 'local'),

      mk('a6', 'aws-s3-role', 'AWS S3 (attached role)',
         'Instance profile, ECS task role or EKS IRSA', 'aws', 's3', 'ambient',
         { env: { bucket: 'AKG_AWS_S3_BUCKET', region: 'AKG_AWS_REGION' } }, 'aws-dev'),

      mk('a7', 'azure-blob-cli', 'Azure Blob (az login)',
         'Uses the token az login left on this machine', 'azure', 'blob_storage',
         // The command is a key from a fixed allowlist, never a command line: free text
         // would be remote code execution for anyone who can edit an endpoint.
         'command',
         { command: 'az_cli_token',
           env: { account: 'AKG_AZURE_STORAGE_ACCOUNT',
                  container: 'AKG_AZURE_STORAGE_CONTAINER' } }, 'local'),

      mk('a8', 'azure-blob-sp', 'Azure Blob (service principal)',
         'Client id and secret supplied by the environment', 'azure', 'blob_storage',
         'client_credentials',
         { env: { account: 'AKG_AZURE_STORAGE_ACCOUNT',
                  tenant_id: 'AKG_AZURE_TENANT_ID', client_id: 'AKG_AZURE_CLIENT_ID',
                  client_secret: 'AKG_AZURE_CLIENT_SECRET' } }, 'azure-dev'),

      mk('a9', 'azure-blob-msi', 'Azure Blob (managed identity)',
         'Workload identity inside Azure; no secret at all', 'azure', 'blob_storage',
         'ambient', { env: { account: 'AKG_AZURE_STORAGE_ACCOUNT' } }, 'azure-prod'),

      mk('a10', 'pubmed-ftp', 'PubMed baseline (NCBI)',
         'Public FTP origin of the annual baseline', 'local', 'ftp', 'anonymous',
         { host: 'ftp.ncbi.nlm.nih.gov', path: '/pubmed/baseline/',
           env: { base_url: 'AKG_PUBMED_BASELINE_URL' } }, 'local'),
    ];
    return of(this.page(all.filter((e) =>
      (!f.provider || e.provider === f.provider) && (!f.env || e.env === f.env))));
  }

  lineage(mioId: string): Observable<MioLineageResp> {
    if (mioId === 'm2') {
      return of({ mio_id: mioId, generated: [],
        produced_from: [{ mio_id: 'm1', code: 'pubmed-csr-graph', name: 'PubMed CSR graph',
                          data_instance_exec_id: 'e1' }] });
    }
    if (mioId === 'm1') {
      return of({ mio_id: mioId, produced_from: [],
        generated: [{ mio_id: 'm2', code: 'pubmed-vector-index', name: 'PubMed vector index',
                      data_instance_exec_id: 'e1' }] });
    }
    return of({ mio_id: mioId, produced_from: [], generated: [] });
  }

  live(): Observable<boolean> {
    return of(false);
  }
}

