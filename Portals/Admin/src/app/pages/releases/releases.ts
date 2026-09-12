import { Component, computed, inject, signal } from '@angular/core';
import { DecimalPipe, PercentPipe } from '@angular/common';
import { Api } from '../../core/api';
import { Release, armLabel, armOk, gateFailures, margin } from '../../core/models';

@Component({
  selector: 'page-releases',
  imports: [DecimalPipe, PercentPipe],
  templateUrl: './releases.html',
  styleUrl: './releases.scss',
})
export class Releases {
  private readonly api = inject(Api);
  readonly all = signal<Release[]>(this.api.releases());
  readonly selected = signal<Release | null>(null);
  readonly confirmText = signal('');
  readonly promoted = signal<string | null>(null);

  readonly armLabel = armLabel;
  readonly armOk = armOk;
  readonly margin = margin;

  readonly live = computed(() => this.all().find((r) => r.state === 'live'));
  readonly candidates = computed(() => this.all().filter((r) => r.state === 'candidate'));

  failures(r: Release): string[] {
    return gateFailures(r, this.live());
  }

  passes(r: Release): boolean {
    return this.failures(r).length === 0;
  }

  delta(r: Release, field: 'test_accuracy' | 'coverage'): number | null {
    const l = this.live();
    if (!l || l.release === r.release) return null;
    return r[field] - l[field];
  }

  select(r: Release): void {
    this.selected.set(r);
    this.confirmText.set('');
    this.promoted.set(null);
  }

  onConfirm(e: Event): void {
    this.confirmText.set((e.target as HTMLInputElement).value);
  }

  /** Promotion needs the gate to pass AND the release id typed exactly. A single
   *  click is not enough for an action that changes what every query resolves. */
  canPromote(r: Release): boolean {
    return this.passes(r) && this.confirmText().trim() === r.release;
  }

  promote(r: Release): void {
    if (!this.canPromote(r)) return;
    this.promoted.set(r.release);
  }

  rollback(): void {
    // One action, by design: the pointer moves back to the prior compatible manifest.
    this.promoted.set('rolled-back');
  }

  close(): void { this.selected.set(null); }

  stateChip(s: Release['state']): string {
    return {
      live: 'chip chip-ok',
      candidate: 'chip chip-run',
      rejected: 'chip chip-fail',
      superseded: 'chip chip-neutral',
    }[s];
  }
}
