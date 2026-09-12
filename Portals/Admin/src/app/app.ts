import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Api } from './core/api';

interface TopNavItem {
  path: string;
  label: string;
  /** Routes in the product but not yet built. Shown, marked, and not linked -- an
   *  operator should see the shape of the product without being misled about it. */
  planned?: boolean;
}

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  private readonly api = inject(Api);
  readonly tenant = this.api.tenant;
  readonly env = this.api.env;

  readonly nav = signal<TopNavItem[]>([
    { path: '/datasets', label: 'DataSets' },
    { path: '/data-management', label: 'Data Management' },
    { path: '/traces', label: 'Traces' },
    { path: '/releases', label: 'Releases' },
    { path: '/operations', label: 'Operations', planned: true },
    { path: '/access', label: 'Access', planned: true },
  ]);
}
