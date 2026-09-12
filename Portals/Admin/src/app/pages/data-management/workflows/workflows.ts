import { Component, inject, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { Api } from '../../../core/api';
import { WorkflowDefinition, stackLabel } from '../../../core/models';

@Component({
  selector: 'page-workflows',
  imports: [JsonPipe],
  templateUrl: './workflows.html',
  styleUrl: './workflows.scss',
})
export class Workflows {
  private readonly api = inject(Api);
  readonly defs = signal<WorkflowDefinition[]>(this.api.workflowDefinitions());
  readonly selected = signal<WorkflowDefinition | null>(null);
  readonly values = signal<Record<string, string | boolean>>({});
  readonly submitted = signal<string | null>(null);

  readonly stackLabel = stackLabel;

  open(def: WorkflowDefinition): void {
    const seed: Record<string, string | boolean> = {};
    for (const p of def.params) if (p.default !== undefined) seed[p.name] = p.default;
    this.values.set(seed);
    this.submitted.set(null);
    this.selected.set(def);
  }

  close(): void { this.selected.set(null); }

  set(name: string, e: Event): void {
    const el = e.target as HTMLInputElement | HTMLSelectElement;
    const v = el instanceof HTMLInputElement && el.type === 'checkbox' ? el.checked : el.value;
    this.values.update((m) => ({ ...m, [name]: v }));
  }

  get missing(): string[] {
    const def = this.selected();
    if (!def) return [];
    const v = this.values();
    return def.params
      .filter((p) => p.required && (v[p.name] === undefined || v[p.name] === ''))
      .map((p) => p.label);
  }

  trigger(): void {
    const def = this.selected();
    if (!def || this.missing.length) return;
    // The portal sends domain/sub_domain/workflow/input_data only. It never names an
    // engine -- the orchestrator resolves tech_stack from config (ADR-008).
    this.submitted.set(crypto.randomUUID());
  }
}
