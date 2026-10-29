import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./components/dashboard/dashboard').then(m => m.DashboardComponent) },
  { path: 'processes', loadComponent: () => import('./components/process-list/process-list').then(m => m.ProcessListComponent) },
  { path: 'processes/:id/edit', loadComponent: () => import('./components/process-editor/process-editor').then(m => m.ProcessEditorComponent) },
  { path: 'processes/:id/record', loadComponent: () => import('./components/recording/recording').then(m => m.RecordingComponent) },
  { path: 'processes/:id', loadComponent: () => import('./components/process-editor/process-editor').then(m => m.ProcessEditorComponent) },
  { path: 'executions/:executionId', loadComponent: () => import('./components/execution-view/execution-view').then(m => m.ExecutionViewComponent) },
  { path: 'pipelines', loadComponent: () => import('./components/pipelines/pipeline-list').then(m => m.PipelineListComponent) },
  { path: 'pipelines/:id', loadComponent: () => import('./components/pipelines/workflow-editor').then(m => m.WorkflowEditorComponent) },
  { path: 'robots', loadComponent: () => import('./components/robots/robots').then(m => m.RobotsComponent) },
  { path: 'docs', loadComponent: () => import('./components/documentation/documentation').then(m => m.DocumentationComponent) },
  { path: 'settings', loadComponent: () => import('./components/settings/settings').then(m => m.SettingsComponent) },
  { path: 'login', loadComponent: () => import('./components/login/login').then(m => m.LoginComponent) },
  { path: '**', redirectTo: '' },
];
