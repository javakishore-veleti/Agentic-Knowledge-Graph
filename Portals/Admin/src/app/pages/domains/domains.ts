import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { CatalogApi } from '../../core/catalog-api';
import { DomainDto } from '../../core/catalog-models';
import { Pager } from '../../shared/pager';

@Component({
  selector: 'page-domains',
  imports: [DatePipe, Pager],
  templateUrl: './domains.html',
  styleUrl: './domains.scss',
})
export class Domains {
  private readonly api = inject(CatalogApi);

  readonly rows = signal<DomainDto[]>([]);
  readonly total = signal(0);
  readonly nextCursor = signal<string | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly query = signal('');

  /** Visited cursors. Opaque cursors cannot be walked backwards, so "previous" is a
   *  stack rather than an offset subtraction. */
  private readonly history = signal<(string | undefined)[]>([]);

  constructor() {
    this.load();
  }

  load(cursor?: string): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.domains({ cursor, q: this.query() || undefined }).subscribe({
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

  onQuery(e: Event): void {
    this.query.set((e.target as HTMLInputElement).value);
    this.history.set([]);
    this.load();
  }
}
