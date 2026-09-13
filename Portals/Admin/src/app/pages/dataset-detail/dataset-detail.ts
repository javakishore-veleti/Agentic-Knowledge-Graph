import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CatalogApi } from '../../core/catalog-api';
import {
  DatasetDto, DatasetEndpointDto, humanBytes, locationStateChip, roleLabel,
} from '../../core/catalog-models';
import { Accordion } from '../../shared/accordion';

/** A dataset is too much for a side panel: versions, every location it lives in with
 *  acquisition state, and the workflows that maintain it. A page also has a URL worth
 *  pasting into a ticket. */
@Component({
  selector: 'page-dataset-detail',
  imports: [DatePipe, RouterLink, Accordion],
  templateUrl: './dataset-detail.html',
  styleUrl: './dataset-detail.scss',
})
export class DatasetDetail {
  private readonly api = inject(CatalogApi);
  private readonly route = inject(ActivatedRoute);

  readonly humanBytes = humanBytes;
  readonly locationStateChip = locationStateChip;
  readonly roleLabel = roleLabel;

  readonly dataset = signal<DatasetDto | null>(null);
  readonly versions = signal<DatasetDto[]>([]);
  readonly locations = signal<DatasetEndpointDto[]>([]);
  readonly loading = signal(true);
  readonly notFound = signal(false);
  readonly notice = signal<string | null>(null);

  readonly sources = computed(() => this.locations().filter((l) => l.role === 'source'));
  readonly destinations = computed(() => this.locations().filter((l) => l.role !== 'source'));
  readonly stored = computed(() => this.destinations().reduce((a, l) => a + l.bytes, 0));
  readonly unavailable = computed(
    () => this.destinations().filter((l) => l.state !== 'available').length);

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    this.api.datasets().subscribe({
      next: (p) => {
        const found = p.items.find((d) => d.dataset_id === id) ?? null;
        this.dataset.set(found);
        this.notFound.set(!found);
        if (found) {
          // Other versions of the same logical dataset, newest first.
          this.versions.set(p.items
            .filter((d) => d.code === found.code && d.domain_id === found.domain_id)
            .sort((a, b) => b.created_at.localeCompare(a.created_at)));
          this.api.datasetLocations(found.dataset_id).subscribe({
            next: (r) => this.locations.set(r.items),
            error: () => this.locations.set([]),
          });
        }
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); this.notFound.set(true); },
    });
  }

  shipsEdges(d: DatasetDto): boolean { return d.adapter !== 'generic-extraction'; }

  /** Acquiring an available copy is refused by the service; not offering it is clearer. */
  canAcquire(l: DatasetEndpointDto): boolean {
    return l.role !== 'source' && l.state !== 'available' && l.state !== 'syncing';
  }

  /** Per-destination outcome. A single page-level notice let one row's result
   *  overwrite another's, which matters here because the accordion shows every
   *  destination at once. */
  readonly notes = signal<Record<string, { kind: 'ok' | 'warn' | 'bad'; text: string }>>({});
  private pollTimer: ReturnType<typeof setInterval> | null = null;

  ngOnDestroy(): void {
    if (this.pollTimer) clearInterval(this.pollTimer);
  }

  acquire(l: DatasetEndpointDto): void {
    const id = l.dataset_endpoint_id;
    this.note(id, 'ok', 'Requesting…');
    this.api.acquire(id, false).subscribe({
      next: (r) => {
        if (r.started) {
          this.note(id, 'ok',
            `Workflow triggered${r.dag_run_id ? ` (run ${r.dag_run_id})` : ''}. ` +
            `Airflow reports back when the data lands.`);
          this.patch(id, { state: 'syncing', sync_wf_status: 'RUNNING' });
          this.syncPolling();
        } else if (r.reason === 'already_available') {
          // Not re-downloading what is already here is the feature, not a failure.
          this.note(id, 'ok', 'Already downloaded. Nothing to do.');
          this.patch(id, { state: 'available' });
        } else {
          this.note(id, 'warn', `Not started: ${r.reason}.`);
        }
      },
      error: (e) => this.note(id, 'bad',
        e?.error?.detail ??
        'Could not reach the Data Management service on :9002. ' +
        'Check it with: npm run local:middleware:status-all'),
    });
  }

  /** Poll only while a run is live, and stop when none is: a timer left running against
   *  an idle page is a request every few seconds forever. */
  private syncPolling(): void {
    const running = this.destinations().filter(
      (d) => d.state === 'syncing' || d.sync_wf_status === 'RUNNING');
    if (!running.length) {
      if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
      return;
    }
    if (this.pollTimer) return;
    this.pollTimer = setInterval(() => {
      for (const d of this.destinations().filter(
        (x) => x.state === 'syncing' || x.sync_wf_status === 'RUNNING')) {
        this.api.acquisitionStatus(d.dataset_endpoint_id).subscribe({
          next: (s) => {
            this.patch(d.dataset_endpoint_id, {
              state: s.state as DatasetEndpointDto['state'],
              sync_wf_status: s.sync_wf_status,
              bytes: s.bytes,
            });
            if (s.state === 'available') {
              this.note(d.dataset_endpoint_id, 'ok',
                `Downloaded ${s.bytes.toLocaleString()} bytes.`);
            } else if (s.state === 'failed') {
              this.note(d.dataset_endpoint_id, 'bad',
                `The workflow failed: ${JSON.stringify(s.error ?? {})}`);
            }
            this.syncPolling();
          },
          error: () => { /* a transient poll failure is not worth a banner */ },
        });
      }
    }, 3000);
  }

  private patch(id: string, changes: Partial<DatasetEndpointDto>): void {
    this.locations.update((list) =>
      list.map((d) => (d.dataset_endpoint_id === id ? { ...d, ...changes } : d)));
  }

  private note(id: string, kind: 'ok' | 'warn' | 'bad', text: string): void {
    this.notes.update((n) => ({ ...n, [id]: { kind, text } }));
  }
}
