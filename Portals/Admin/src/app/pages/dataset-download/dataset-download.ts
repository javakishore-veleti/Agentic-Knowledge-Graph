import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CatalogApi } from '../../core/catalog-api';
import {
  DatasetDto, DatasetEndpointDto, locationStateChip,
} from '../../core/catalog-models';

/** Download a dataset from its source into one destination.
 *
 * The page is a list of destinations, not a single button, because a dataset version can
 * land in several places -- the local filesystem, S3, Blob storage -- and each is an
 * independent copy with its own state and its own workflow run. Downloading to S3 says
 * nothing about whether the local copy exists.
 *
 * Nothing here transfers data. The button asks the Data Management service, which claims
 * the endpoint and triggers Airflow; the DAG downloads and calls the catalog back. So the
 * page polls rather than waits: a corpus download outlives any HTTP request.
 */
@Component({
  selector: 'akg-dataset-download',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dataset-download.html',
  styleUrl: './dataset-download.scss',
})
export class DatasetDownload {
  private readonly api = inject(CatalogApi);
  private readonly route = inject(ActivatedRoute);

  readonly dataset = signal<DatasetDto | null>(null);
  readonly source = signal<DatasetEndpointDto | null>(null);
  readonly destinations = signal<DatasetEndpointDto[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  /** Per-destination note, keyed by endpoint id: one row's outcome must not overwrite
   *  another's, which a single page-level message would do. */
  readonly notes = signal<Record<string, { kind: 'ok' | 'warn' | 'bad'; text: string }>>({});
  readonly busy = signal<Record<string, boolean>>({});

  private readonly datasetId = this.route.snapshot.paramMap.get('id') ?? '';
  private pollTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    this.load();
  }

  ngOnDestroy(): void {
    if (this.pollTimer) clearInterval(this.pollTimer);
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.datasets({ limit: 200 }).subscribe({
      next: (page) => {
        const d = page.items.find((x) => x.dataset_id === this.datasetId) ?? null;
        this.dataset.set(d);
        this.loadEndpoints();
      },
      error: () => {
        this.loading.set(false);
        this.error.set('Could not reach the DataCatalog service on :9001.');
      },
    });
  }

  private loadEndpoints(): void {
    this.api.datasetLocations(this.datasetId).subscribe({
      next: (r) => {
        this.source.set(r.items.find((i) => i.role === 'source') ?? null);
        this.destinations.set(r.items.filter((i) => i.role !== 'source'));
        this.loading.set(false);
        this.syncPolling();
      },
      error: () => {
        this.loading.set(false);
        this.error.set('Could not load this dataset’s locations.');
      },
    });
  }

  stateChip = locationStateChip;

  /** Already-available data is not re-downloaded. Offering the button anyway would
   *  invite a click the service answers with "already_available", which reads as a
   *  failure to anyone who did not write the service. */
  canDownload(d: DatasetEndpointDto): boolean {
    return d.state !== 'available' && d.state !== 'syncing' && !this.busy()[d.dataset_endpoint_id];
  }

  isRunning(d: DatasetEndpointDto): boolean {
    return d.state === 'syncing' || d.sync_wf_status === 'RUNNING';
  }

  download(d: DatasetEndpointDto): void {
    const id = d.dataset_endpoint_id;
    this.busy.update((b) => ({ ...b, [id]: true }));
    this.note(id, 'ok', 'Requesting…');

    this.api.acquire(id, false).subscribe({
      next: (r) => {
        this.busy.update((b) => ({ ...b, [id]: false }));
        if (r.started) {
          this.note(id, 'ok',
            `Workflow triggered${r.dag_run_id ? ` (run ${r.dag_run_id})` : ''}. ` +
            `Airflow reports back when the data lands.`);
          this.patch(id, { state: 'syncing', sync_wf_status: 'RUNNING' });
          this.syncPolling();
        } else if (r.reason === 'already_available') {
          // Not a failure: not re-downloading what is already here is the feature.
          this.note(id, 'ok', 'Already downloaded. Nothing to do.');
          this.patch(id, { state: 'available' });
        } else {
          this.note(id, 'warn', `Not started: ${r.reason}.`);
        }
      },
      error: (e) => {
        this.busy.update((b) => ({ ...b, [id]: false }));
        this.note(id, 'bad',
          e?.error?.detail ??
          'Could not reach the Data Management service on :9002. ' +
          'Check it with: npm run local:middleware:status-all');
      },
    });
  }

  /** Poll only while something is running, and stop when nothing is. A timer left
   *  running against an idle page is a request every few seconds forever. */
  private syncPolling(): void {
    const running = this.destinations().filter((d) => this.isRunning(d));
    if (!running.length) {
      if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
      return;
    }
    if (this.pollTimer) return;
    this.pollTimer = setInterval(() => {
      for (const d of this.destinations().filter((x) => this.isRunning(x))) {
        this.api.acquisitionStatus(d.dataset_endpoint_id).subscribe({
          next: (s) => {
            this.patch(d.dataset_endpoint_id, {
              state: s.state as DatasetEndpointDto['state'],
              sync_wf_status: s.sync_wf_status,
              bytes: s.bytes,
              object_count: s.object_count ?? d.object_count,
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
    this.destinations.update((list) =>
      list.map((d) => (d.dataset_endpoint_id === id ? { ...d, ...changes } : d)));
  }

  private note(id: string, kind: 'ok' | 'warn' | 'bad', text: string): void {
    this.notes.update((n) => ({ ...n, [id]: { kind, text } }));
  }
}
