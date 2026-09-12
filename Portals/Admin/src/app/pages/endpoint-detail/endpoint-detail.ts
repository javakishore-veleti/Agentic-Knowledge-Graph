import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CatalogApi } from '../../core/catalog-api';
import {
  AppEndpointDto, connectionTypeLabel, providerChip, providerLabel,
} from '../../core/catalog-models';
import { Accordion } from '../../shared/accordion';

/** Full page rather than a drawer.
 *
 * An endpoint carries connection facts, variable names, resolution status, usage and
 * provenance. A side panel forces all of that into a narrow column and scrolls it away;
 * a page with accordions lets each part be opened where it belongs and keeps the URL
 * shareable. */
@Component({
  selector: 'page-endpoint-detail',
  imports: [RouterLink, Accordion],
  templateUrl: './endpoint-detail.html',
  styleUrl: './endpoint-detail.scss',
})
export class EndpointDetail {
  private readonly api = inject(CatalogApi);
  private readonly route = inject(ActivatedRoute);

  readonly providerLabel = providerLabel;
  readonly connectionTypeLabel = connectionTypeLabel;
  readonly providerChip = providerChip;

  readonly endpoint = signal<AppEndpointDto | null>(null);
  readonly loading = signal(true);
  readonly notFound = signal(false);

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    this.api.endpoints().subscribe({
      next: (p) => {
        const found = p.items.find((e) => e.app_endpoint_id === id) ?? null;
        this.endpoint.set(found);
        this.notFound.set(!found);
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); this.notFound.set(true); },
    });
  }

  /** Non-secret connection facts: host, port, database, bucket, profile. */
  readonly facts = computed(() => {
    const d = this.endpoint()?.connection_details ?? {};
    return Object.entries(d)
      .filter(([k]) => k !== 'env')
      .map(([k, v]) => ({ k, v: String(v) }));
  });

  /** Environment variable NAMES. Values live in the environment, never here. */
  readonly envVars = computed(() => {
    const env = this.endpoint()?.connection_details?.env ?? {};
    return Object.entries(env).map(([k, v]) => ({ k, v: String(v) }));
  });

  /** What the connection type means in practice, and what it needs from the machine. */
  readonly connectionExplainer = computed(() => {
    const e = this.endpoint();
    if (!e) return '';
    return {
      basic_auth: 'A username stored here and a password supplied by the environment.',
      token: 'A static token supplied by the environment.',
      client_credentials:
        'A service principal: tenant and client id, with the secret from the environment.',
      command:
        'A credential helper run on the host. Only helpers from a fixed allowlist are ' +
        'permitted — a free-text command here would be remote code execution for anyone ' +
        'who can edit an endpoint.',
      env_vars: 'Everything comes from the named environment variables below.',
      profile: 'A named profile in a credentials file on the machine running the code.',
      ambient:
        'Whatever identity the host already has: an attached role, a managed identity, ' +
        'or application default credentials. Nothing to configure and no secret to leak.',
      anonymous: 'A public endpoint needing no credential.',
    }[e.connection_type] ?? '';
  });

  detailsJson(): string {
    return JSON.stringify(this.endpoint()?.connection_details ?? {}, null, 2);
  }
}
