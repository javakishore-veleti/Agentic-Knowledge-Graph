import { Component, inject, signal } from '@angular/core';
import { CatalogApi } from '../../core/catalog-api';
import { WorkflowDto } from '../../core/catalog-models';

/** The master list. A workflow is a first-class row with parameter definitions, which is
 *  what lets the MIO page render a trigger form instead of hard-coding one per workflow. */
@Component({
  selector: 'page-workflows-master',
  templateUrl: './workflows-master.html',
  styleUrl: './workflows-master.scss',
})
export class WorkflowsMaster {
  private readonly api = inject(CatalogApi);
  readonly rows = signal<WorkflowDto[]>([]);
  readonly loading = signal(true);
  readonly showInactive = signal(false);
  readonly query = signal('');

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.workflows({ q: this.query() || undefined }).subscribe({
      next: (p) => { this.rows.set(p.items); this.loading.set(false); },
      error: () => { this.rows.set([]); this.loading.set(false); },
    });
  }

  onQuery(e: Event): void { this.query.set((e.target as HTMLInputElement).value); this.load(); }

  visible(): WorkflowDto[] {
    return this.showInactive() ? this.rows() : this.rows().filter((w) => w.is_active);
  }
}
