import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'datasets', pathMatch: 'full' },
  {
    path: 'datasets',
    loadComponent: () => import('./pages/datasets/datasets').then((m) => m.Datasets),
    title: 'DataSets · Knowledge Admin',
  },
  {
    path: 'data-management',
    loadComponent: () =>
      import('./pages/data-management/data-management').then((m) => m.DataManagement),
    title: 'Data Management · Knowledge Admin',
    children: [
      { path: '', redirectTo: 'workflows', pathMatch: 'full' },
      {
        path: 'workflows',
        loadComponent: () =>
          import('./pages/data-management/workflows/workflows').then((m) => m.Workflows),
      },
      {
        path: 'batches',
        loadComponent: () =>
          import('./pages/data-management/batches/batches').then((m) => m.Batches),
      },
      {
        path: 'executions',
        loadComponent: () =>
          import('./pages/data-management/executions/executions').then((m) => m.Executions),
      },
    ],
  },
  {
    path: 'traces',
    loadComponent: () => import('./pages/traces/traces').then((m) => m.Traces),
    title: 'Traces · Knowledge Admin',
  },
  {
    path: 'releases',
    loadComponent: () => import('./pages/releases/releases').then((m) => m.Releases),
    title: 'Releases · Knowledge Admin',
  },
  { path: '**', redirectTo: 'datasets' },
];
