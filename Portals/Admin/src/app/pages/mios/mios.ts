import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { CatalogApi } from '../../core/catalog-api';
import {
  DataInstanceDto, DomainDto, MIO_STATES, MioDto, MioLineageResp, MioState,
  MioWorkflowDto, TECH_STACKS, WorkflowDto, WorkflowParamDto, humanBytes,
  instanceKindChip, mioStateChip, techLabel,
} from '../../core/catalog-models';
import { Pager } from '../../shared/pager';

type Tab = 'overview' | 'instances' | 'workflows' | 'lineage';

@Component({
  selector: 'page-mios',
  imports: [DatePipe, DecimalPipe, Pager],
  templateUrl: './mios.html',
  styleUrl: './mios.scss',
})
export class Mios {
  private readonly api = inject(CatalogApi);

  readonly techLabel = techLabel;
  readonly humanBytes = humanBytes;
  readonly mioStateChip = mioStateChip;
  readonly instanceKindChip = instanceKindChip;
  readonly techStacks = TECH_STACKS;
  readonly states = MIO_STATES;

  readonly rows = signal<MioDto[]>([]);
  readonly domains = signal<DomainDto[]>([]);
  readonly total = signal(0);
  readonly nextCursor = signal<string | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly notice = signal<string | null>(null);

  readonly domain = signal('');
  readonly state = signal('');
  readonly cdcOnly = signal(false);
  readonly query = signal('');
  private readonly history = signal<(string | undefined)[]>([]);

  // ---- detail drawer
  readonly selected = signal<MioDto | null>(null);
  readonly tab = signal<Tab>('overview');
  readonly instances = signal<DataInstanceDto[]>([]);
  readonly cdcInstanceId = signal<string | null>(null);
  readonly attached = signal<MioWorkflowDto[]>([]);
  readonly masterWorkflows = signal<WorkflowDto[]>([]);
  readonly lineage = signal<MioLineageResp | null>(null);

  // ---- create / edit
  readonly editing = signal<MioDto | null>(null);
  readonly creating = signal(false);
  readonly form = signal<Record<string, string>>({});

  // ---- invoke
  readonly invoking = signal<MioWorkflowDto | null>(null);
  readonly invokeValues = signal<Record<string, unknown>>({});
  readonly invokeResult = signal<string | null>(null);

  readonly summary = computed(() => {
    const r = this.rows();
    return {
      live: r.filter((m) => m.state === 'live').length,
      unvalidated: r.filter((m) => !m.validations_pass).length,
      documents: r.reduce((a, m) => a + m.documents_count, 0),
      edges: r.reduce((a, m) => a + m.edges_count, 0),
    };
  });

  constructor() {
    this.api.domains().subscribe({ next: (p) => this.domains.set(p.items), error: () => {} });
    this.api.workflows().subscribe({ next: (p) => this.masterWorkflows.set(p.items), error: () => {} });
    this.load();
  }

  load(cursor?: string): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.mios({
      cursor,
      domain: this.domain() || undefined,
      state: this.state() || undefined,
      has_cdc: this.cdcOnly() ? true : undefined,
      q: this.query() || undefined,
    }).subscribe({
      next: (p) => {
        this.rows.set(p.items);
        this.total.set(p.page.total);
        this.nextCursor.set(p.page.next_cursor);
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(e?.error?.detail ?? 'Could not reach the DataCatalog service.');
        this.loading.set(false);
      },
    });
  }

  private reset(): void { this.history.set([]); this.load(); }

  setDomain(e: Event): void { this.domain.set((e.target as HTMLSelectElement).value); this.reset(); }
  setState(s: string): void { this.state.set(this.state() === s ? '' : s); this.reset(); }
  toggleCdc(): void { this.cdcOnly.update((v) => !v); this.reset(); }
  onQuery(e: Event): void { this.query.set((e.target as HTMLInputElement).value); this.reset(); }

  next(): void {
    const c = this.nextCursor();
    if (!c) return;
    this.history.update((h) => [...h, c]);
    this.load(c);
  }
  prev(): void {
    const h = [...this.history()]; h.pop(); this.history.set(h); this.load(h[h.length - 1]);
  }
  canPrev(): boolean { return this.history().length > 0; }

  // ---- drawer -----------------------------------------------------------

  open(m: MioDto, tab: Tab = 'overview'): void {
    this.selected.set(m);
    this.tab.set(tab);
    this.invokeResult.set(null);
    this.api.instances(m.mio_id).subscribe({
      next: (r) => { this.instances.set(r.items); this.cdcInstanceId.set(r.cdc_instance_id); },
      error: () => { this.instances.set([]); this.cdcInstanceId.set(null); },
    });
    this.api.mioWorkflows(m.mio_id).subscribe({
      next: (r) => this.attached.set(r.items), error: () => this.attached.set([]),
    });
    this.api.lineage(m.mio_id).subscribe({
      next: (r) => this.lineage.set(r), error: () => this.lineage.set(null),
    });
  }

  closeDrawer(): void { this.selected.set(null); this.invoking.set(null); }

  /** Workflows in the master list that are active and not already attached. */
  readonly attachable = computed(() => {
    const have = new Set(this.attached().map((w) => w.workflow_id));
    return this.masterWorkflows().filter((w) => w.is_active && !have.has(w.workflow_id));
  });

  attach(e: Event): void {
    const id = (e.target as HTMLSelectElement).value;
    const m = this.selected();
    if (!id || !m) return;
    this.api.attachWorkflow(m.mio_id, id, 'build').subscribe({
      next: () => { this.refreshWorkflows(m.mio_id); this.load(); },
      error: (err) => this.notice.set(err?.error?.detail ?? 'Could not attach the workflow.'),
    });
    (e.target as HTMLSelectElement).value = '';
  }

  detach(w: MioWorkflowDto): void {
    const m = this.selected();
    if (!m || !w.workflow_id) return;
    this.api.detachWorkflow(m.mio_id, w.workflow_id).subscribe({
      next: () => { this.refreshWorkflows(m.mio_id); this.load(); },
      error: (err) => this.notice.set(err?.error?.detail ?? 'Could not detach the workflow.'),
    });
  }

  private refreshWorkflows(mioId: string): void {
    this.api.mioWorkflows(mioId).subscribe({ next: (r) => this.attached.set(r.items) });
  }

  // ---- invoke -----------------------------------------------------------

  startInvoke(w: MioWorkflowDto): void {
    const seed: Record<string, unknown> = {};
    for (const p of w.params_json) if (p.default !== undefined) seed[p.name] = p.default;
    this.invokeValues.set(seed);
    this.invokeResult.set(null);
    this.invoking.set(w);
  }

  setParam(name: string, e: Event): void {
    const el = e.target as HTMLInputElement | HTMLSelectElement;
    const v = el instanceof HTMLInputElement && el.type === 'checkbox' ? el.checked : el.value;
    this.invokeValues.update((m) => ({ ...m, [name]: v }));
  }

  /** Required parameters, reported before submitting — the service refuses these too,
   *  but showing them here avoids a round trip to learn what is missing. */
  readonly missingParams = computed(() => {
    const w = this.invoking();
    if (!w) return [] as string[];
    const v = this.invokeValues();
    return w.params_json
      .filter((p: WorkflowParamDto) => p.required && (v[p.name] === undefined || v[p.name] === ''))
      .map((p) => p.label);
  });

  runInvoke(): void {
    const m = this.selected();
    const w = this.invoking();
    if (!m || !w?.workflow_id || this.missingParams().length) return;
    this.api.invokeWorkflow(m.mio_id, w.workflow_id, this.invokeValues()).subscribe({
      next: (r) => this.invokeResult.set(
        `Queued · exec ${r.data_instance_exec_id} · status ${r.status}` +
        (r.wf_ref_id ? ` · engine ref ${r.wf_ref_id}` : ' · no engine reference yet')),
      error: (err) => this.notice.set(err?.error?.detail ?? 'The workflow could not be started.'),
    });
  }

  // ---- create / edit ----------------------------------------------------

  startCreate(): void {
    this.creating.set(true);
    this.editing.set(null);
    this.form.set({ domain_code: this.domains()[0]?.code ?? '', tech_stack: 'csr_graph' });
  }

  startEdit(m: MioDto): void {
    this.editing.set(m);
    this.creating.set(false);
    this.form.set({
      name: m.name, tech_stack: m.tech_stack, state: m.state,
      pinned_version: m.pinned_version ?? '',
    });
  }

  setField(k: string, e: Event): void {
    const v = (e.target as HTMLInputElement | HTMLSelectElement).value;
    this.form.update((f) => ({ ...f, [k]: v }));
  }

  cancelForm(): void { this.creating.set(false); this.editing.set(null); }

  saveForm(): void {
    const f = this.form();
    this.notice.set(null);
    if (this.creating()) {
      this.api.createMio({
        domain_code: f['domain_code'], code: f['code'] ?? '', name: f['name'] ?? '',
        description: f['description'] ?? '', tech_stack: f['tech_stack'],
      }).subscribe({
        next: () => { this.cancelForm(); this.reset(); },
        error: (err) => this.notice.set(err?.error?.detail ?? 'Could not create the MIO.'),
      });
      return;
    }
    const m = this.editing();
    if (!m) return;
    this.api.updateMio({
      mio_id: m.mio_id, name: f['name'], tech_stack: f['tech_stack'],
      state: f['state'] as MioState,
      pinned_version: f['pinned_version'] || null,
    }).subscribe({
      next: () => { this.cancelForm(); this.load(); this.closeDrawer(); },
      // The service refuses promotion without a pin or with failing validations, and
      // says which. Surfacing its message beats inventing one here.
      error: (err) => this.notice.set(err?.error?.detail ?? 'Could not update the MIO.'),
    });
  }

  remove(m: MioDto): void {
    this.api.deleteMio(m.mio_id).subscribe({
      next: () => { this.closeDrawer(); this.reset(); },
      error: (err) => this.notice.set(err?.error?.detail ?? 'Could not delete the MIO.'),
    });
  }

  validationEntries(m: MioDto): { key: string; ok: boolean }[] {
    return Object.entries(m.validations ?? {}).map(([key, ok]) => ({ key, ok: !!ok }));
  }
}
