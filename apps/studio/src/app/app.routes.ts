import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./components/dashboard/dashboard').then(m => m.DashboardComponent) },
  { path: 'processes', loadComponent: () => import('./components/process-list/process-list').then(m => m.ProcessListComponent) },
  { path: 'processes/:id/edit', loadComponent: () => import('./components/process-editor/process-editor').then(m => m.ProcessEditorComponent) },
  { path: 'processes/:id', loadComponent: () => import('./components/process-editor/process-editor').then(m => m.ProcessEditorComponent) },
  { path: 'processes/:id/record', loadComponent: () => import('./components/recording/recording').then(m => m.RecordingComponent) },
  { path: 'executions/:executionId', loadComponent: () => import('./components/execution-view/execution-view').then(m => m.ExecutionViewComponent) },
  { path: '**', redirectTo: '' },
];
