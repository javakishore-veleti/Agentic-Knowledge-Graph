import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'mios', pathMatch: 'full' },
  {
    path: 'domains',
    loadComponent: () => import('./pages/domains/domains').then((m) => m.Domains),
    title: 'Domains · Knowledge Admin',
  },
  {
    path: 'datasets',
    loadComponent: () => import('./pages/datasets/datasets').then((m) => m.Datasets),
    title: 'DataSets · Knowledge Admin',
  },
  {
    path: 'datasets/:id',
    loadComponent: () =>
      import('./pages/dataset-detail/dataset-detail').then((m) => m.DatasetDetail),
    title: 'Dataset · Knowledge Admin',
  },
  {
    path: 'mios',
    loadComponent: () => import('./pages/mios/mios').then((m) => m.Mios),
    title: 'MIOs · Knowledge Admin',
  },
  {
    path: 'workflows',
    loadComponent: () =>
      import('./pages/workflows/workflows-master').then((m) => m.WorkflowsMaster),
    title: 'Workflows · Knowledge Admin',
  },
  {
    path: 'endpoints',
    loadComponent: () =>
      import('./pages/data-management/endpoints/endpoints').then((m) => m.Endpoints),
    title: 'Endpoints · Knowledge Admin',
  },
  {
    path: 'endpoints/:id',
    loadComponent: () =>
      import('./pages/endpoint-detail/endpoint-detail').then((m) => m.EndpointDetail),
    title: 'Endpoint · Knowledge Admin',
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
      {
        path: 'endpoints',
        loadComponent: () =>
          import('./pages/data-management/endpoints/endpoints').then((m) => m.Endpoints),
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
  { path: '**', redirectTo: 'mios' },
];
