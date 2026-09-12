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
  { path: '**', redirectTo: 'datasets' },
];
