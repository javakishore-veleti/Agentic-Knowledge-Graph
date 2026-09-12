import { Component, computed, inject, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { Api } from '../../../core/api';
import { WorkflowExecution, WorkflowStatus, statusChip, stackLabel } from '../../../core/models';

@Component({
  selector: 'page-executions',
  imports: [JsonPipe],
  templateUrl: './executions.html',
  styleUrl: './executions.scss',
})
export class Executions {
  private readonly api = inject(Api);
  readonly all = signal<WorkflowExecution[]>(this.api.executions());
  readonly status = signal<'all' | WorkflowStatus>('all');
  readonly expanded = signal<string | null>(null);

  readonly statusChip = statusChip;
  readonly stackLabel = stackLabel;

  readonly rows = computed(() => {
    const s = this.status();
    return s === 'all' ? this.all() : this.all().filter((e) => e.status === s);
  });

  /** PENDING with no engine id past a grace period is a submit that never landed --
   *  the wf_exec_stuck view. Surfacing it is the whole point of writing the row first. */
  stuck(e: WorkflowExecution): boolean {
    if (e.status !== 'PENDING' || e.wf_ref_id) return false;
    return Date.now() - new Date(e.created_at).getTime() > 5 * 60_000;
  }

  readonly stuckCount = computed(() => this.all().filter((e) => this.stuck(e)).length);

  toggle(id: string): void {
    this.expanded.update((cur) => (cur === id ? null : id));
  }

  setStatus(s: 'all' | WorkflowStatus): void { this.status.set(s); }

  duration(e: WorkflowExecution): string {
    if (!e.started_at) return '—';
    const end = e.finished_at ? new Date(e.finished_at).getTime() : Date.now();
    const secs = Math.round((end - new Date(e.started_at).getTime()) / 1000);
    if (secs < 60) return `${secs}s`;
    if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
    return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
  }
}
