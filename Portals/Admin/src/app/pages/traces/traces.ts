import { Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe, PercentPipe } from '@angular/common';
import { Api } from '../../core/api';
import { Trace, routeChip, routeLabel } from '../../core/models';

@Component({
  selector: 'page-traces',
  imports: [DecimalPipe, PercentPipe],
  templateUrl: './traces.html',
  styleUrl: './traces.scss',
})
export class Traces {
  private readonly api = inject(Api);
  readonly all = signal<Trace[]>(this.api.traces());
  readonly query = signal('');
  readonly openId = signal<string | null>(this.api.traces()[0]?.answer_id ?? null);

  readonly routeLabel = routeLabel;
  readonly routeChip = routeChip;

  readonly rows = computed(() => {
    const q = this.query().trim().toLowerCase();
    if (!q) return this.all();
    return this.all().filter(
      (t) =>
        t.answer_id.toLowerCase().includes(q) ||
        t.trace_id.toLowerCase().includes(q) ||
        t.question.toLowerCase().includes(q),
    );
  });

  readonly open = computed(() => this.all().find((t) => t.answer_id === this.openId()) ?? null);

  onQuery(e: Event): void { this.query.set((e.target as HTMLInputElement).value); }
  select(id: string): void { this.openId.set(id); }

  dispositionChip(d: Trace['disposition']): string {
    return d === 'ANSWER' ? 'chip chip-ok' : d === 'REFUSE' ? 'chip chip-warn' : 'chip chip-run';
  }

  /** The calibrated value is what the threshold is compared against, never the raw
   *  posterior. Showing both makes the calibration bias visible. */
  bias(t: Trace): number | null {
    if (t.raw_confidence === undefined || t.calibrated_confidence === undefined) return null;
    return t.calibrated_confidence - t.raw_confidence;
  }

  admittedCount(t: Trace): number {
    return t.candidates.filter((c) => c.admitted).length;
  }

  /** Audit export. The whole chain, as JSON, for a reviewer outside this portal. */
  exportTrace(t: Trace): void {
    const blob = new Blob([JSON.stringify(t, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${t.answer_id}.trace.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
}
