import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, InjectionToken, inject, signal } from '@angular/core';
import { Observable, of } from 'rxjs';
import {
  AppEndpointDto, DataInstanceDto, DataInstanceExecDto, DataInstancesResp, DatasetDto,
  DomainDto, MioDto, MioLineageResp, Paged,
} from './catalog-models';

/** What the portal needs from the DataCatalog service.
 *
 * Two implementations: HTTP against the real API, and a mock for working on the UI
 * without the stack up. Components depend on this token and never on either class. */
export abstract class CatalogApi {
  abstract domains(): Observable<Paged<DomainDto>>;
  abstract datasets(filters?: { domain?: string; adapter?: string; q?: string }): Observable<Paged<DatasetDto>>;
  abstract mios(filters?: { domain?: string; state?: string; tech_stack?: string; has_cdc?: boolean; q?: string }): Observable<Paged<MioDto>>;
  abstract instances(mioId: string): Observable<DataInstancesResp>;
  abstract execs(instanceId: string): Observable<Paged<DataInstanceExecDto>>;
  abstract endpoints(filters?: { tech_stack?: string; env?: string }): Observable<Paged<AppEndpointDto>>;
  abstract lineage(mioId: string): Observable<MioLineageResp>;
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

  domains(): Observable<Paged<DomainDto>> {
    return this.http.get<Paged<DomainDto>>(`${this.base}/api/v1/domains`);
  }

  datasets(f: { domain?: string; adapter?: string; q?: string } = {}): Observable<Paged<DatasetDto>> {
    return this.http.get<Paged<DatasetDto>>(`${this.base}/api/v1/datasets`, { params: this.params(f) });
  }

  mios(f: { domain?: string; state?: string; tech_stack?: string; has_cdc?: boolean; q?: string } = {}): Observable<Paged<MioDto>> {
    return this.http.get<Paged<MioDto>>(`${this.base}/api/v1/mios`, { params: this.params(f) });
  }

  instances(mioId: string): Observable<DataInstancesResp> {
    return this.http.get<DataInstancesResp>(`${this.base}/api/v1/mios/${mioId}/instances`);
  }

  execs(instanceId: string): Observable<Paged<DataInstanceExecDto>> {
    return this.http.get<Paged<DataInstanceExecDto>>(`${this.base}/api/v1/instances/${instanceId}/execs`);
  }

  endpoints(f: { tech_stack?: string; env?: string } = {}): Observable<Paged<AppEndpointDto>> {
    return this.http.get<Paged<AppEndpointDto>>(`${this.base}/api/v1/app-endpoints`, { params: this.params(f) });
  }

  lineage(mioId: string): Observable<MioLineageResp> {
    return this.http.get<MioLineageResp>(`${this.base}/api/v1/mios/${mioId}/lineage`);
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

  datasets(f: { domain?: string; adapter?: string; q?: string } = {}): Observable<Paged<DatasetDto>> {
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

  mios(f: { domain?: string; state?: string; tech_stack?: string; has_cdc?: boolean; q?: string } = {}): Observable<Paged<MioDto>> {
    const all: MioDto[] = [
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
    return of(this.page(all.filter((m) =>
      (!f.domain || m.domain_code === f.domain) &&
      (!f.state || m.state === f.state) &&
      (!f.tech_stack || m.tech_stack === f.tech_stack) &&
      (f.has_cdc === undefined || m.has_cdc === f.has_cdc) &&
      (!f.q || (m.name + m.code).toLowerCase().includes(f.q.toLowerCase())))));
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

  endpoints(f: { tech_stack?: string; env?: string } = {}): Observable<Paged<AppEndpointDto>> {
    const all: AppEndpointDto[] = [
      { app_endpoint_id: 'a1', code: 'pg-local', name: 'Local Postgres', tech_stack: 'postgres',
        env: 'local', host: 'localhost', port: 5432, database: 'akg',
        options: { sslmode: 'disable' }, secret_ref: 'kv://akg-local/pg-password', is_active: true },
      { app_endpoint_id: 'a2', code: 'pgvector-local', name: 'Local pgvector', tech_stack: 'pgvector',
        env: 'local', host: 'localhost', port: 5432, database: 'akg',
        options: { index: 'doc_embeddings' }, secret_ref: 'kv://akg-local/pg-password', is_active: true },
      { app_endpoint_id: 'a3', code: 'os-local', name: 'Local OpenSearch', tech_stack: 'opensearch',
        env: 'local', host: 'localhost', port: 9200, database: null,
        options: { index: 'documents' }, secret_ref: null, is_active: true },
      { app_endpoint_id: 'a4', code: 'pg-azure-dev', name: 'Azure Postgres dev', tech_stack: 'postgres',
        env: 'azure-dev', host: 'akg-dev.postgres.database.azure.com', port: 5432, database: 'akg',
        options: { sslmode: 'require' }, secret_ref: 'kv://akg-dev/pg-password', is_active: true },
      { app_endpoint_id: 'a5', code: 'redpanda-local', name: 'Local Redpanda', tech_stack: 'kafka',
        env: 'local', host: 'localhost', port: 9092, database: null,
        options: { topic_prefix: 'akg' }, secret_ref: null, is_active: true },
    ];
    return of(this.page(all.filter((e) =>
      (!f.tech_stack || e.tech_stack === f.tech_stack) && (!f.env || e.env === f.env))));
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

