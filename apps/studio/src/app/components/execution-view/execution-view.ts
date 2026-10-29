import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
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
          <span *ngIf="isLive" class="live-indicator">LIVE</span>
          <div class="header-actions">
            <button *ngIf="execution.status === 'running'" class="btn-ghost btn-sm" (click)="pauseExecution()">Pause</button>
            <button *ngIf="execution.status === 'paused'" class="btn-primary btn-sm" (click)="resumeExecution()">Resume</button>
            <button *ngIf="execution.status === 'running' || execution.status === 'paused'" class="btn-ghost btn-sm btn-danger-text" (click)="cancelExecution()">Cancel</button>
            <button *ngIf="isTerminal()" class="btn-primary btn-sm" (click)="reRun()">Re-run</button>
          </div>
        </div>
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">Execution ID</span>
            <span class="mono">{{ execution.id | slice:0:8 }}...</span>
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

      <!-- Steps -->
      <div class="section" *ngIf="steps.length">
        <h2 class="section-title">Steps <span class="step-count">({{ steps.length }})</span></h2>
        <div class="steps-list">
          <div *ngFor="let step of steps; let i = index" class="step-row" [ngClass]="step.status">
            <div class="step-header" (click)="toggleStep(i)">
              <div class="step-marker">
                <svg *ngIf="step.status === 'succeeded'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                <svg *ngIf="step.status === 'failed'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                <span *ngIf="step.status === 'running'" class="dot-running"></span>
                <span *ngIf="step.status !== 'succeeded' && step.status !== 'failed' && step.status !== 'running'" class="dot-pending"></span>
              </div>
              <span class="step-index">Step {{ step.step_index + 1 }}</span>
              <span class="mono step-id">{{ step.step_id }}</span>
              <span class="badge sm" [ngClass]="step.status">{{ step.status }}</span>
              <span class="duration mono" *ngIf="step.started_at && step.completed_at">{{ getDuration(step) }}ms</span>
              <svg class="expand-icon" [class.expanded]="expandedSteps.has(i)" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <div class="step-details" *ngIf="expandedSteps.has(i)">
              <div class="detail-grid">
                <div class="detail-item" *ngIf="step.started_at">
                  <span class="detail-label">Started</span>
                  <span class="mono">{{ step.started_at | date:'HH:mm:ss.SSS' }}</span>
                </div>
                <div class="detail-item" *ngIf="step.completed_at">
                  <span class="detail-label">Completed</span>
                  <span class="mono">{{ step.completed_at | date:'HH:mm:ss.SSS' }}</span>
                </div>
              </div>
              <div class="step-error" *ngIf="step.error">
                <span class="detail-label">Error</span>
                <pre class="mono error-pre">{{ step.error | json }}</pre>
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
    .header-actions { margin-left: auto; display: flex; gap: 6px; }
    .live-indicator {
      font-size: 10px; font-weight: 700; letter-spacing: .08em;
      color: var(--color-green); background: var(--color-green-bg);
      padding: 2px 8px; border-radius: 10px; animation: pulse 1.5s infinite;
    }
    .meta-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
    .meta-label { display: block; font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: .05em; margin-bottom: 4px; }
    .mono { font-family: var(--font-mono); font-size: 12px; }
    .btn-danger-text { color: var(--color-red) !important; }

    .section { margin-bottom: 24px; }
    .section-title { margin-bottom: 12px; }
    .step-count { color: var(--text-muted); font-weight: 400; }

    .steps-list { border: 1px solid var(--border-color); border-radius: var(--radius-lg); overflow: hidden; }
    .step-row { border-bottom: 1px solid var(--border-subtle); }
    .step-row:last-child { border-bottom: none; }
    .step-header {
      display: flex; align-items: center; gap: 12px;
      padding: 10px 16px; cursor: pointer; transition: background 0.1s;
    }
    .step-header:hover { background: var(--bg-hover); }
    .step-marker {
      width: 24px; height: 24px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    }
    .step-row.succeeded .step-marker { background: var(--color-green-bg); color: var(--color-green); }
    .step-row.failed .step-marker { background: var(--color-red-bg); color: var(--color-red); }
    .step-row.running .step-marker { background: var(--color-blue-bg); }
    .dot-running { width: 8px; height: 8px; border-radius: 50%; background: var(--color-blue); animation: pulse 1s infinite; }
    .dot-pending { width: 8px; height: 8px; border-radius: 50%; background: var(--bg-tertiary); }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

    .step-index { font-weight: 600; font-size: 13px; }
    .step-id { color: var(--text-muted); }
    .badge.sm { font-size: 10px; padding: 1px 6px; }
    .duration { color: var(--text-muted); margin-left: auto; }
    .expand-icon { color: var(--text-muted); transition: transform 0.15s; flex-shrink: 0; }
    .expand-icon.expanded { transform: rotate(180deg); }

    .step-details {
      padding: 0 16px 12px 52px;
      background: var(--bg-secondary); border-top: 1px solid var(--border-subtle);
    }
    .detail-grid { display: flex; gap: 32px; padding-top: 10px; }
    .detail-item { }
    .detail-label { display: block; font-size: 10px; text-transform: uppercase; color: var(--text-muted); letter-spacing: .05em; margin-bottom: 2px; }
    .step-error { margin-top: 8px; }
    .error-pre { background: var(--color-red-bg); color: var(--color-red); padding: 8px 12px; border-radius: var(--radius-md); font-size: 12px; white-space: pre-wrap; margin-top: 4px; }

    .error-title { color: var(--color-red); }
    .error-block { background: var(--color-red-bg); color: var(--color-red); padding: 16px; border-radius: var(--radius-lg); white-space: pre-wrap; }
    .output-block { background: var(--bg-surface); border: 1px solid var(--border-color); padding: 16px; border-radius: var(--radius-lg); white-space: pre-wrap; }
  `]
})
export class ExecutionViewComponent implements OnInit, OnDestroy {
  execution: Execution | null = null;
  steps: ExecutionStep[] = [];
  expandedSteps = new Set<number>();
  isLive = false;

  private execId = '';
  private pollTimer: any = null;
  private ws: WebSocket | null = null;

  constructor(
    private api: ApiService,
    private route: ActivatedRoute,
    private router: Router,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit() {
    this.execId = this.route.snapshot.paramMap.get('executionId')!;
    this.loadExecution();
    this.loadSteps();
    this.connectWebSocket();
  }

  ngOnDestroy() {
    this.stopPolling();
    if (this.ws) { this.ws.close(); this.ws = null; }
  }

  loadExecution() {
    this.api.getExecution(this.execId).subscribe({
      next: e => {
        this.execution = e;
        this.isLive = e.status === 'running' || e.status === 'paused';
        if (this.isLive && !this.pollTimer) this.startPolling();
        if (!this.isLive) this.stopPolling();
        this.cdr.detectChanges();
      }
    });
  }

  loadSteps() {
    this.api.getExecutionSteps(this.execId).subscribe({
      next: s => { this.steps = s; this.cdr.detectChanges(); }
    });
  }

  private startPolling() {
    this.pollTimer = setInterval(() => {
      this.loadExecution();
      this.loadSteps();
    }, 2000);
  }

  private stopPolling() {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
  }

  private connectWebSocket() {
    try {
      this.ws = this.api.connectExecutionWs(this.execId);
      this.ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === 'step_update' || msg.type === 'execution_update') {
            this.loadExecution();
            this.loadSteps();
          }
        } catch {}
      };
      this.ws.onerror = () => {};
      this.ws.onclose = () => { this.ws = null; };
    } catch {}
  }

  toggleStep(index: number) {
    if (this.expandedSteps.has(index)) {
      this.expandedSteps.delete(index);
    } else {
      this.expandedSteps.add(index);
    }
  }

  isTerminal(): boolean {
    const s = this.execution?.status;
    return s === 'succeeded' || s === 'failed' || s === 'cancelled';
  }

  pauseExecution() {
    this.api.pauseExecution(this.execId).subscribe({ next: () => this.loadExecution() });
  }

  resumeExecution() {
    this.api.resumeExecution(this.execId).subscribe({ next: () => this.loadExecution() });
  }

  cancelExecution() {
    this.api.cancelExecution(this.execId).subscribe({ next: () => this.loadExecution() });
  }

  reRun() {
    if (!this.execution) return;
    this.api.createExecution(this.execution.process_id, this.execution.version_id).subscribe({
      next: newExec => {
        this.api.startExecution(newExec.id).subscribe({
          next: () => this.router.navigate(['/executions', newExec.id])
        });
      }
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
