import { Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Api } from '../../../core/api';
import { WorkflowBatch, statusChip, stackLabel } from '../../../core/models';

@Component({
  selector: 'page-batches',
  imports: [DecimalPipe],
  templateUrl: './batches.html',
  styleUrl: './batches.scss',
})
export class Batches {
  private readonly api = inject(Api);
  readonly rows = signal<WorkflowBatch[]>(this.api.batches());
  readonly statusChip = statusChip;
  readonly stackLabel = stackLabel;

  readonly summary = computed(() => {
    const r = this.rows();
    return {
      running: r.filter((b) => b.status === 'RUNNING' || b.status === 'SUBMITTED').length,
      failed: r.filter((b) => b.status === 'FAILED').length,
      units: r.reduce((a, b) => a + b.total_count, 0),
      failedUnits: r.reduce((a, b) => a + b.failed_count, 0),
    };
  });

  open(b: WorkflowBatch): number {
    return b.total_count - b.succeeded_count - b.failed_count;
  }

  pct(b: WorkflowBatch, part: 'ok' | 'failed'): number {
    if (!b.total_count) return 0;
    const n = part === 'ok' ? b.succeeded_count : b.failed_count;
    return (n / b.total_count) * 100;
  }

  /** A batch claiming a terminal status while detail rows are still open is the
   *  inconsistency the wf_batch_inconsistent view surfaces. */
  inconsistent(b: WorkflowBatch): boolean {
    const terminal = b.status === 'SUCCEEDED' || b.status === 'FAILED' || b.status === 'CANCELLED';
    return terminal && this.open(b) > 0;
  }
}
