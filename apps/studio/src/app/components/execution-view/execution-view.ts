import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { Execution, ExecutionStep } from '../../models/process.model';

@Component({
  selector: 'app-execution-view',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="page" *ngIf="execution">
      <div class="breadcrumb">
        <a routerLink="/processes">Processes</a>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        <a [routerLink]="['/processes', execution.process_id]">Process</a>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        <span>Execution</span>
      </div>

      <div class="exec-header card">
        <div class="header-top">
          <h1>Execution</h1>
          <span class="badge" [ngClass]="execution.status">{{ execution.status }}</span>
        </div>
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">Execution ID</span>
            <span class="mono">{{ execution.id }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Started</span>
            <span class="mono">{{ execution.started_at ? (execution.started_at | date:'MMM d, HH:mm:ss') : '—' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Completed</span>
            <span class="mono">{{ execution.completed_at ? (execution.completed_at | date:'MMM d, HH:mm:ss') : '—' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Duration</span>
            <span class="mono">{{ getTotalDuration() }}</span>
          </div>
        </div>
      </div>

      <!-- Steps Timeline -->
      <div class="section" *ngIf="steps.length">
        <h2 class="section-title">Steps</h2>
        <div class="timeline">
          <div *ngFor="let step of steps" class="timeline-item" [ngClass]="step.status">
            <div class="timeline-marker">
              <svg *ngIf="step.status === 'succeeded'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
              <svg *ngIf="step.status === 'failed'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              <span *ngIf="step.status === 'running'" class="dot-running"></span>
              <span *ngIf="step.status !== 'succeeded' && step.status !== 'failed' && step.status !== 'running'" class="dot-pending"></span>
            </div>
            <div class="timeline-content">
              <div class="timeline-header">
                <span class="step-index">Step {{ step.step_index + 1 }}</span>
                <span class="mono step-id">{{ step.step_id }}</span>
                <span class="badge" [ngClass]="step.status">{{ step.status }}</span>
                <span class="duration mono" *ngIf="step.started_at && step.completed_at">{{ getDuration(step) }}ms</span>
              </div>
              <div class="step-error" *ngIf="step.error">
                <pre class="mono">{{ step.error | json }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Error -->
      <div class="section" *ngIf="execution.error">
        <h2 class="section-title error-title">Error</h2>
        <pre class="error-block mono">{{ execution.error | json }}</pre>
      </div>

      <!-- Outputs -->
      <div class="section" *ngIf="execution.outputs">
        <h2 class="section-title">Outputs</h2>
        <pre class="output-block mono">{{ execution.outputs | json }}</pre>
      </div>
    </div>
  `,
  styles: [`
    .page { padding: 32px; max-width: 1000px; }
    .breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-muted); margin-bottom: 20px; }
    .breadcrumb a { color: var(--text-accent); }
    .breadcrumb span:last-child { color: var(--text-primary); }

    .exec-header { margin-bottom: 24px; }
    .header-top { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
    .meta-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
    .meta-item { }
    .meta-label { display: block; font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: .05em; margin-bottom: 4px; }
    .mono { font-family: var(--font-mono); font-size: 12px; }

    .section { margin-bottom: 24px; }
    .section-title { margin-bottom: 12px; }

    .timeline { display: flex; flex-direction: column; }
    .timeline-item {
      display: flex;
      gap: 16px;
      padding: 12px 0;
      border-bottom: 1px solid var(--border-subtle);
    }
    .timeline-marker {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .timeline-item.succeeded .timeline-marker { background: var(--color-green-bg); color: var(--color-green); }
    .timeline-item.failed .timeline-marker { background: var(--color-red-bg); color: var(--color-red); }
    .timeline-item.running .timeline-marker { background: var(--color-blue-bg); }
    .dot-running { width: 8px; height: 8px; border-radius: 50%; background: var(--color-blue); animation: pulse 1s infinite; }
    .dot-pending { width: 8px; height: 8px; border-radius: 50%; background: var(--bg-tertiary); }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

    .timeline-content { flex: 1; min-width: 0; }
    .timeline-header { display: flex; align-items: center; gap: 12px; }
    .step-index { font-weight: 600; font-size: 13px; }
    .step-id { color: var(--text-muted); }
    .duration { color: var(--text-muted); margin-left: auto; }
    .step-error { margin-top: 8px; }
    .step-error pre { background: var(--color-red-bg); color: var(--color-red); padding: 8px 12px; border-radius: var(--radius-md); font-size: 12px; white-space: pre-wrap; }

    .error-title { color: var(--color-red); }
    .error-block { background: var(--color-red-bg); color: var(--color-red); padding: 16px; border-radius: var(--radius-lg); white-space: pre-wrap; }
    .output-block { background: var(--bg-surface); border: 1px solid var(--border-color); padding: 16px; border-radius: var(--radius-lg); white-space: pre-wrap; }
  `]
})
export class ExecutionViewComponent implements OnInit {
  execution: Execution | null = null;
  steps: ExecutionStep[] = [];

  constructor(private api: ApiService, private route: ActivatedRoute) {}

  ngOnInit() {
    const execId = this.route.snapshot.paramMap.get('executionId')!;
    this.api.getExecution(execId).subscribe({
      next: e => this.execution = e,
      error: () => {}
    });
    this.api.getExecutionSteps(execId).subscribe({
      next: s => this.steps = s,
      error: () => {}
    });
  }

  getDuration(step: ExecutionStep): number {
    if (!step.started_at || !step.completed_at) return 0;
    return new Date(step.completed_at).getTime() - new Date(step.started_at).getTime();
  }

  getTotalDuration(): string {
    if (!this.execution?.started_at || !this.execution?.completed_at) return '—';
    const ms = new Date(this.execution.completed_at).getTime() - new Date(this.execution.started_at).getTime();
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
}
