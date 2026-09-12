import { Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Api } from '../../core/api';
import { DataSet } from '../../core/models';

@Component({
  selector: 'page-datasets',
  imports: [DecimalPipe],
  templateUrl: './datasets.html',
  styleUrl: './datasets.scss',
})
export class Datasets {
  private readonly api = inject(Api);
  readonly all = signal<DataSet[]>(this.api.datasets());
  readonly filter = signal<'all' | DataSet['state']>('all');
  readonly query = signal('');

  readonly rows = computed(() => {
    const f = this.filter();
    const q = this.query().trim().toLowerCase();
    return this.all().filter((d) => {
      if (f !== 'all' && d.state !== f) return false;
      if (!q) return true;
      return (
        d.name.toLowerCase().includes(q) ||
        d.source_version.toLowerCase().includes(q) ||
        d.domain.toLowerCase().includes(q)
      );
    });
  });

  readonly totals = computed(() => {
    const rows = this.all();
    return {
      sets: rows.length,
      live: rows.filter((d) => d.state === 'live').length,
      documents: rows.reduce((a, d) => a + d.documents, 0),
      edges: rows.reduce((a, d) => a + d.edges, 0),
      // A set that fails either check is not promotable, whatever its state says.
      unverified: rows.filter((d) => !d.alignment_assert || !d.source_recount).length,
    };
  });

  stateChip(s: DataSet['state']): string {
    return {
      live: 'chip chip-ok',
      ready: 'chip chip-run',
      building: 'chip chip-warn',
      rejected: 'chip chip-fail',
    }[s];
  }

  setFilter(f: 'all' | DataSet['state']): void { this.filter.set(f); }
  onQuery(e: Event): void { this.query.set((e.target as HTMLInputElement).value); }
}
