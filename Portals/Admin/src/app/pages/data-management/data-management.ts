import { Component, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

interface SideNavItem {
  path: string;
  label: string;
  hint: string;
  planned?: boolean;
}

@Component({
  selector: 'page-data-management',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './data-management.html',
  styleUrl: './data-management.scss',
})
export class DataManagement {
  readonly sections = signal<SideNavItem[]>([
    { path: 'workflows', label: 'Workflows', hint: 'Trigger and schedule' },
    { path: 'batches', label: 'Batches', hint: 'One row per batch instance' },
    { path: 'executions', label: 'Executions', hint: 'wf_exec_log detail' },
    { path: 'sources', label: 'Sources', hint: 'Registry and adapters', planned: true },
    { path: 'ontology', label: 'Ontology', hint: 'Aliases and blocked words', planned: true },
    { path: 'freshness', label: 'Freshness', hint: 'Deltas and retractions', planned: true },
  ]);
}
