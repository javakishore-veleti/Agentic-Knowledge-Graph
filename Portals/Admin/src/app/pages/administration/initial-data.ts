import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { CatalogApi } from '../../core/catalog-api';
import { InitialDataStatusDto } from '../../core/catalog-models';
import { Accordion } from '../../shared/accordion';

interface EntityCopy {
  title: string;
  what: string;
  why: string;
}

/** First-run loading.
 *
 * On a blank database every list in the portal is empty, and an administrator cannot tell
 * "nothing has been loaded yet" from "something is broken". This screen answers that and
 * gives each entity a button.
 *
 * Order is enforced by the catalog rather than by this page: datasets carry a foreign key
 * to domains, so loading them first would fail at the constraint. The page reads the
 * order the catalog states, so the two cannot drift. */
@Component({
  selector: 'page-initial-data',
  imports: [DatePipe, Accordion],
  templateUrl: './initial-data.html',
  styleUrl: './initial-data.scss',
})
export class InitialData {
  private readonly api = inject(CatalogApi);

  readonly rows = signal<InitialDataStatusDto[]>([]);
  readonly loading = signal(true);
  readonly busy = signal<string | null>(null);
  readonly message = signal<{ kind: 'ok' | 'warn' | 'bad'; text: string } | null>(null);
  /** Why the list is empty. Without this the page rendered its heading and nothing else
   *  when the service was unreachable, which looks like "there is nothing to load"
   *  rather than "I could not ask". */
  readonly error = signal<string | null>(null);

  readonly copy: Record<string, EntityCopy> = {
    purposes: {
      title: 'Purposes',
      what: 'The vocabulary describing what a workflow is for — initial dataset loading, indexing, calibration, evaluation.',
      why: 'Loaded first because workflow definitions reference it by foreign key.',
    },
    domains: {
      title: 'Domains',
      what: 'The top of the catalog: biomedical, enterprise. Everything else hangs off a domain.',
      why: 'Datasets carry a foreign key to a domain, so nothing else can load until this has.',
    },
    endpoints: {
      title: 'Endpoints',
      what: 'Example endpoints beyond the system set — a scratch path, a NAS mount.',
      why: 'The eleven system endpoints already exist: they ship with the product because they describe how the platform reaches storage, not what data it holds.',
    },
    datasets: {
      title: 'DataSets',
      what: 'Reference source datasets with their versions, adapters and locations.',
      why: 'Needs domains. Each dataset also gets its source and destination locations.',
    },
    workflows: {
      title: 'Workflows',
      what: 'The master workflow list with parameter definitions, so MIOs have something to attach and invoke.',
      why: 'Needs purposes, since every workflow declares one.',
    },
  };

  readonly ordered = computed(
    () => [...this.rows()].sort((a, b) => a.load_order - b.load_order));

  readonly allLoaded = computed(
    () => this.rows().length > 0 && this.rows().every((r) => r.last_status === 'SUCCEEDED'));

  readonly nextStep = computed(
    () => this.ordered().find((r) => r.last_status !== 'SUCCEEDED') ?? null);

  constructor() { this.refresh(); }

  refresh(): void {
    this.error.set(null);
    // Also clear the last action's banner. A failure message that outlives the refresh
    // sits above rows that have since loaded and contradicts them.
    this.message.set(null);
    this.api.initialDataStatus().subscribe({
      next: (r) => {
        this.rows.set(r.items);
        this.error.set(r.items.length ? null
          : 'The service returned no entities to load, which should not happen.');
        this.loading.set(false);
      },
      error: (e) => {
        this.rows.set([]);
        this.loading.set(false);
        this.error.set(
          e?.error?.detail ??
          `Could not reach the DataCatalog service. Check it is running: ` +
          `npm run local:middleware:status-all`);
      },
    });
  }

  /** A prerequisite that has not loaded yet. The catalog refuses these too; disabling the
   *  button just avoids making someone press it to find out. */
  blockedBy(r: InitialDataStatusDto): string | null {
    if (!r.depends_on) return null;
    const dep = this.rows().find((x) => x.entity === r.depends_on);
    return dep && dep.row_count > 0 ? null : r.depends_on;
  }

  canLoad(r: InitialDataStatusDto): boolean {
    return r.last_status !== 'SUCCEEDED' && !this.blockedBy(r) && this.busy() === null;
  }

  load(r: InitialDataStatusDto, force = false): void {
    this.busy.set(r.entity);
    this.message.set(null);
    this.api.loadInitialData(r.entity, force).subscribe({
      next: (res) => {
        this.busy.set(null);
        if (res.claimed) {
          this.message.set({ kind: 'ok',
            text: `${this.copy[r.entity]?.title ?? r.entity} load started.` +
                  (res.tracker_id ? ` Tracker ${res.tracker_id}.` : '') });
        } else if (res.reason === 'already_loaded') {
          // The tracker's whole purpose. Re-running would be harmless but would report a
          // fresh load that changed nothing, which reads as progress.
          this.message.set({ kind: 'warn',
            text: `Already loaded. Nothing was run — use Reload only if you mean to.` });
        } else if (res.reason === 'already_running') {
          this.message.set({ kind: 'warn', text: 'A load for this is already running.' });
        } else if (res.reason.startsWith('requires_')) {
          this.message.set({ kind: 'bad',
            text: `Load ${res.reason.replace('requires_', '')} first.` });
        } else {
          this.message.set({ kind: 'bad', text: res.reason });
        }
        this.refresh();
      },
      error: () => {
        this.busy.set(null);
        this.message.set({ kind: 'bad', text: 'The catalog service could not be reached.' });
      },
    });
  }

  statusChip(r: InitialDataStatusDto): string {
    if (r.last_status === 'SUCCEEDED') return 'chip chip-ok';
    if (r.last_status === 'FAILED') return 'chip chip-fail';
    if (r.last_status === 'RUNNING' || r.last_status === 'PENDING') return 'chip chip-run';
    return 'chip chip-warn';
  }

  statusText(r: InitialDataStatusDto): string {
    if (r.last_status === 'SUCCEEDED') return '✓ loaded';
    if (r.last_status) return r.last_status.toLowerCase();
    return 'not loaded';
  }
}
