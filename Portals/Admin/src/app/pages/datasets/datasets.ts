import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { CatalogApi } from '../../core/catalog-api';
import { DatasetDto, DomainDto } from '../../core/catalog-models';
import { errorText } from '../../core/http-error';
import { Pager } from '../../shared/pager';

/** Source data at a version.
 *
 * This page deliberately shows no document counts, edge counts, validations or state:
 * those describe the produced artifact and live on the MIO (ADR-009). A dataset is
 * immutable once acquired, so a new version is a new row rather than an edit. */
@Component({
  selector: 'page-datasets',
  imports: [DatePipe, RouterLink, Pager],
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


  /** One entry per logical dataset, newest version first.
   *
   *  The list shows ONE row per dataset rather than expanding every version inline: a
   *  table of four rows headed "3 datasets" reads as a miscount, and the version history
   *  now lives on the detail page where it has room.
   *
   *  Caveat worth knowing: the API paginates by version row, so a dataset with many
   *  versions could straddle a page boundary and appear on both. Fixing that properly
   *  needs a dataset-level list endpoint rather than grouping in the browser. */
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
        this.error.set(errorText(e, 'Could not reach the DataCatalog service.'));
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
}
