import { Component, computed, inject, signal } from '@angular/core';
import { CatalogApi } from '../../../core/catalog-api';
import { AppEndpointDto, authModeLabel, techLabel } from '../../../core/catalog-models';

/** Where each technology lives.
 *
 * Several endpoints may exist for one technology — a local Postgres and an Azure one, two
 * OpenSearch clusters — so results are grouped by technology rather than collapsed to it.
 *
 * No credential is shown because none exists to show: the catalog stores a Key Vault
 * reference, never a secret. */
@Component({
  selector: 'page-endpoints',
  templateUrl: './endpoints.html',
  styleUrl: './endpoints.scss',
})
export class Endpoints {
  private readonly api = inject(CatalogApi);
  readonly techLabel = techLabel;
  readonly authModeLabel = authModeLabel;

  readonly rows = signal<AppEndpointDto[]>([]);
  readonly loading = signal(true);
  readonly env = signal('');

  readonly envs = computed(() => [...new Set(this.rows().map((e) => e.env))].sort());

  readonly grouped = computed(() => {
    const filtered = this.env() ? this.rows().filter((e) => e.env === this.env()) : this.rows();
    const by = new Map<string, AppEndpointDto[]>();
    for (const e of filtered) by.set(e.tech_stack, [...(by.get(e.tech_stack) ?? []), e]);
    return [...by.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  });

  constructor() {
    this.api.endpoints().subscribe({
      next: (p) => { this.rows.set(p.items); this.loading.set(false); },
      error: () => { this.rows.set([]); this.loading.set(false); },
    });
  }

  setEnv(e: string): void { this.env.set(this.env() === e ? '' : e); }

  optionPairs(e: AppEndpointDto): { k: string; v: string }[] {
    return Object.entries(e.options ?? {}).map(([k, v]) => ({ k, v: String(v) }));
  }

  /** The NAMES of the variables this endpoint reads. Never their values -- the catalog
   *  does not hold them, so the portal has nothing to leak. */
  envVars(e: AppEndpointDto): { k: string; v: string }[] {
    return Object.entries(e.config_env ?? {}).map(([k, v]) => ({ k, v: String(v) }));
  }
}
