import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CatalogApi } from '../../../core/catalog-api';
import {
  AppEndpointDto, ConnectionType, Provider, connectionTypeLabel, providerChip,
  providerLabel,
} from '../../../core/catalog-models';

/** The list of endpoints.
 *
 * An endpoint is one WAY of reaching a service. Provider says who runs it, service says
 * which one, connection type says how you authenticate, and connection details carries
 * the rest — non-secret facts at the top level, environment variable NAMES under `env`.
 * Nothing secret is stored, so nothing secret can be shown. */
@Component({
  selector: 'page-endpoints',
  imports: [RouterLink],
  templateUrl: './endpoints.html',
  styleUrl: './endpoints.scss',
})
export class Endpoints {
  private readonly api = inject(CatalogApi);

  readonly providerLabel = providerLabel;
  readonly connectionTypeLabel = connectionTypeLabel;
  readonly providerChip = providerChip;

  readonly rows = signal<AppEndpointDto[]>([]);
  readonly loading = signal(true);
  readonly provider = signal<string>('');
  readonly connType = signal<string>('');

  readonly providers = computed(
    () => [...new Set(this.rows().map((e) => e.provider))].sort() as Provider[]);
  readonly connTypes = computed(
    () => [...new Set(this.rows().map((e) => e.connection_type))].sort() as ConnectionType[]);

  readonly visible = computed(() => this.rows().filter((e) =>
    (!this.provider() || e.provider === this.provider()) &&
    (!this.connType() || e.connection_type === this.connType())));

  constructor() {
    this.api.endpoints().subscribe({
      next: (p) => { this.rows.set(p.items); this.loading.set(false); },
      error: () => { this.rows.set([]); this.loading.set(false); },
    });
  }

  setProvider(p: string): void { this.provider.set(this.provider() === p ? '' : p); }
  setConnType(c: string): void { this.connType.set(this.connType() === c ? '' : c); }

  /** Non-secret facts: host, port, database, bucket, profile. Shown as-is. */
  facts(e: AppEndpointDto): { k: string; v: string }[] {
    return Object.entries(e.connection_details ?? {})
      .filter(([k]) => k !== 'env')
      .map(([k, v]) => ({ k, v: String(v) }));
  }

  /** Environment variable NAMES. The catalog never holds their values. */
  envVars(e: AppEndpointDto): { k: string; v: string }[] {
    return Object.entries(e.connection_details?.env ?? {}).map(([k, v]) => ({ k, v: String(v) }));
  }

  // The drawer is gone: an endpoint carries connection facts, variable names, resolution
  // status, usage and provenance, and a narrow side panel scrolls most of that away.
  // /endpoints/:id is also shareable, which a drawer never is.
}
