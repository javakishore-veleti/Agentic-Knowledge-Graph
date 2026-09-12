import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { CatalogApi } from '../../core/catalog-api';
import {
  DatasetDto, DatasetEndpointDto, humanBytes, locationStateChip, roleLabel,
} from '../../core/catalog-models';
import { Accordion } from '../../shared/accordion';

/** A dataset is too much for a side panel: versions, every location it lives in with
 *  acquisition state, and the workflows that maintain it. A page also has a URL worth
 *  pasting into a ticket. */
@Component({
  selector: 'page-dataset-detail',
  imports: [DatePipe, RouterLink, Accordion],
  templateUrl: './dataset-detail.html',
  styleUrl: './dataset-detail.scss',
})
export class DatasetDetail {
  private readonly api = inject(CatalogApi);
  private readonly route = inject(ActivatedRoute);

  readonly humanBytes = humanBytes;
  readonly locationStateChip = locationStateChip;
  readonly roleLabel = roleLabel;

  readonly dataset = signal<DatasetDto | null>(null);
  readonly versions = signal<DatasetDto[]>([]);
  readonly locations = signal<DatasetEndpointDto[]>([]);
  readonly loading = signal(true);
  readonly notFound = signal(false);
  readonly notice = signal<string | null>(null);

  readonly sources = computed(() => this.locations().filter((l) => l.role === 'source'));
  readonly destinations = computed(() => this.locations().filter((l) => l.role !== 'source'));
  readonly stored = computed(() => this.destinations().reduce((a, l) => a + l.bytes, 0));
  readonly unavailable = computed(
    () => this.destinations().filter((l) => l.state !== 'available').length);

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    this.api.datasets().subscribe({
      next: (p) => {
        const found = p.items.find((d) => d.dataset_id === id) ?? null;
        this.dataset.set(found);
        this.notFound.set(!found);
        if (found) {
          // Other versions of the same logical dataset, newest first.
          this.versions.set(p.items
            .filter((d) => d.code === found.code && d.domain_id === found.domain_id)
            .sort((a, b) => b.created_at.localeCompare(a.created_at)));
          this.api.datasetLocations(found.dataset_id).subscribe({
            next: (r) => this.locations.set(r.items),
            error: () => this.locations.set([]),
          });
        }
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); this.notFound.set(true); },
    });
  }

  shipsEdges(d: DatasetDto): boolean { return d.adapter !== 'generic-extraction'; }

  /** Acquiring an available copy is refused by the service; not offering it is clearer. */
  canAcquire(l: DatasetEndpointDto): boolean {
    return l.role !== 'source' && l.state !== 'available' && l.state !== 'syncing';
  }

  acquire(l: DatasetEndpointDto): void {
    this.notice.set(
      `Would request acquisition from the Data Management service: ` +
      `POST /dataset-endpoints/${l.dataset_endpoint_id}/acquire. The service and the DAG ` +
      `exist; the portal is not wired to them yet.`);
  }
}
