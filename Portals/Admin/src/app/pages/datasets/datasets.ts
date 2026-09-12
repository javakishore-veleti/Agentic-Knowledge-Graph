import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { CatalogApi } from '../../core/catalog-api';
import {
  DatasetDto, DatasetEndpointDto, DomainDto, humanBytes, locationStateChip, roleLabel,
} from '../../core/catalog-models';
import { Pager } from '../../shared/pager';

/** Source data at a version.
 *
 * This page deliberately shows no document counts, edge counts, validations or state:
 * those describe the produced artifact and live on the MIO (ADR-009). A dataset is
 * immutable once acquired, so a new version is a new row rather than an edit. */
@Component({
  selector: 'page-datasets',
  imports: [DatePipe, Pager],
  templateUrl: './datasets.html',
  styleUrl: './datasets.scss',
})
export class Datasets {
  private readonly api = inject(CatalogApi);

  readonly rows = signal<DatasetDto[]>([]);
  readonly domains = signal<DomainDto[]>([]);
  readonly total = signal(0);
  readonly nextCursor = signal<string | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  readonly domain = signal<string>('');
  readonly adapter = signal<string>('');
  readonly query = signal('');

  private readonly history = signal<(string | undefined)[]>([]);

  // ---- detail drawer
  readonly selected = signal<DatasetDto | null>(null);
  readonly selectedVersions = signal<DatasetDto[]>([]);
  readonly locations = signal<DatasetEndpointDto[]>([]);
  readonly locationsLoading = signal(false);
  readonly notice = signal<string | null>(null);

  readonly humanBytes = humanBytes;
  readonly locationStateChip = locationStateChip;
  readonly roleLabel = roleLabel;

  /** Source versions of one logical dataset, newest first. A dataset code with several
   *  versions is the normal case, not a duplicate. */
  readonly grouped = computed(() => {
    const by = new Map<string, DatasetDto[]>();
    for (const d of this.rows()) {
      const key = `${d.domain_id}:${d.code}`;
      by.set(key, [...(by.get(key) ?? []), d]);
    }
    return [...by.values()].map((versions) =>
      [...versions].sort((a, b) => b.created_at.localeCompare(a.created_at)));
  });

  constructor() {
    this.api.domains().subscribe({ next: (p) => this.domains.set(p.items), error: () => {} });
    this.load();
  }

  load(cursor?: string): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.datasets({
      cursor,
      domain: this.domain() || undefined,
      adapter: this.adapter() || undefined,
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
  setAdapter(a: string): void { this.adapter.set(this.adapter() === a ? '' : a); this.reset(); }
  onQuery(e: Event): void { this.query.set((e.target as HTMLInputElement).value); this.reset(); }

  next(): void {
    const c = this.nextCursor();
    if (!c) return;
    this.history.update((h) => [...h, c]);
    this.load(c);
  }

  prev(): void {
    const h = [...this.history()];
    h.pop();
    this.history.set(h);
    this.load(h[h.length - 1]);
  }

  canPrev(): boolean { return this.history().length > 0; }

  /** Edge-bearing sources parse with no model calls; everything else pays for extraction. */
  shipsEdges(d: DatasetDto): boolean { return d.adapter !== 'generic-extraction'; }

  // ---- detail ------------------------------------------------------------

  open(versions: DatasetDto[]): void {
    const newest = versions[0];
    this.selected.set(newest);
    this.selectedVersions.set(versions);
    this.notice.set(null);
    this.locationsLoading.set(true);
    this.api.datasetLocations(newest.dataset_id).subscribe({
      next: (r) => { this.locations.set(r.items); this.locationsLoading.set(false); },
      error: () => { this.locations.set([]); this.locationsLoading.set(false); },
    });
  }

  close(): void { this.selected.set(null); }

  /** Where it came from. Zero of these means nobody can rebuild this dataset. */
  sources(): DatasetEndpointDto[] {
    return this.locations().filter((l) => l.role === 'source');
  }

  /** Copies we hold. */
  destinations(): DatasetEndpointDto[] {
    return this.locations().filter((l) => l.role !== 'source');
  }

  /** A destination is worth acquiring when the data is not already there. Acquiring an
   *  available copy is refused by the service anyway -- this just avoids offering it. */
  canAcquire(l: DatasetEndpointDto): boolean {
    return l.role !== 'source' && l.state !== 'available' && l.state !== 'syncing';
  }

  acquire(l: DatasetEndpointDto): void {
    // The data-mgmt service owns this; the portal does not call Airflow directly.
    this.notice.set(
      `Acquisition for ${l.uri} would be requested from the Data Management service ` +
      `(POST /dataset-endpoints/${l.dataset_endpoint_id}/acquire). Not wired to the ` +
      `portal yet — the service and DAG exist.`,
    );
  }

  totalStored(): number {
    return this.destinations().reduce((a, l) => a + l.bytes, 0);
  }
}
