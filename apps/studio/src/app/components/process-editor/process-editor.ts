import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { Process, ProcessVersion, ProcessStep, Execution } from '../../models/process.model';

@Component({
  selector: 'app-process-editor',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <div class="page" *ngIf="process">
      <!-- Top Bar -->
      <div class="top-bar">
        <div class="breadcrumb">
          <a routerLink="/processes">Processes</a>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
          <span>{{ process.name }}</span>
        </div>
        <div class="top-actions">
          <a [routerLink]="['/processes', process.id, 'record']" class="btn-secondary btn-with-icon">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="6" fill="currentColor"/></svg>
            Record
          </a>
          <button class="btn-primary btn-with-icon" (click)="runExecution()" [disabled]="!selectedVersion || executionRunning">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3" fill="currentColor"/></svg>
            Run
          </button>
          <button class="btn-secondary" *ngIf="executionRunning && !executionPaused" (click)="pauseExecution()">Pause</button>
          <button class="btn-secondary" *ngIf="executionPaused" (click)="resumeExecution()">Resume</button>
          <button class="btn-danger" *ngIf="executionRunning" (click)="cancelExecution()">Cancel</button>
        </div>
      </div>

      <!-- Header -->
      <div class="process-header card">
        <div class="header-info">
          <h1>{{ process.name }}</h1>
          <span class="text-muted">{{ process.description || 'No description' }}</span>
        </div>
        <div class="header-meta">
          <div class="meta-item">
            <span class="meta-label">ID</span>
            <span class="mono">{{ process.id | slice:0:8 }}...</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Created</span>
            <span class="mono">{{ process.created_at | date:'MMM d, yyyy HH:mm' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Versions</span>
            <span>{{ versions.length }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">Executions</span>
            <span>{{ executions.length }}</span>
          </div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button class="tab" [class.active]="activeTab === 'steps'" (click)="activeTab = 'steps'">Steps</button>
        <button class="tab" [class.active]="activeTab === 'versions'" (click)="activeTab = 'versions'">Versions</button>
        <button class="tab" [class.active]="activeTab === 'executions'" (click)="activeTab = 'executions'">Executions</button>
      </div>

      <!-- Steps Tab -->
      <div class="tab-content" *ngIf="activeTab === 'steps'">
        <div class="version-selector" *ngIf="versions.length">
          <label>Version:</label>
          <select [(ngModel)]="selectedVersionId" (ngModelChange)="onVersionChange()">
            <option *ngFor="let v of versions" [value]="v.id">v{{ v.version }} — {{ v.status }}</option>
          </select>
        </div>

        <div class="steps-layout" *ngIf="steps.length">
          <div class="step-list">
            <div *ngFor="let step of steps; let i = index"
                 class="step-item"
                 [class.selected]="selectedStepIndex === i"
                 [class.step-running]="liveState && liveState.current_step_index === i"
                 [class.step-done]="liveState && (liveState.completed_steps || []).includes(step.id)"
                 [class.step-failed]="liveState && (liveState.failed_steps || []).includes(step.id)"
                 (click)="selectedStepIndex = i">
              <span class="step-num">{{ i + 1 }}</span>
              <div class="step-body">
                <span class="step-type-badge">{{ step.type }}</span>
                <span class="step-label">{{ step.label || step.id }}</span>
              </div>
              <span class="step-status-dot" *ngIf="liveState">
                <span *ngIf="liveState.current_step_index === i" class="dot-running"></span>
                <svg *ngIf="(liveState.completed_steps || []).includes(step.id)" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-green)" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                <svg *ngIf="(liveState.failed_steps || []).includes(step.id)" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-red)" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </span>
            </div>
          </div>
          <div class="step-detail card" *ngIf="selectedStep">
            <h3>Step Detail</h3>
            <div class="detail-grid">
              <div class="detail-field">
                <label>ID</label>
                <span class="mono">{{ selectedStep.id }}</span>
              </div>
              <div class="detail-field">
                <label>Type</label>
                <span class="badge created">{{ selectedStep.type }}</span>
              </div>
              <div class="detail-field full">
                <label>Label</label>
                <input [(ngModel)]="selectedStep.label" />
              </div>
              <div class="detail-field full" *ngIf="selectedStep.target">
                <label>Target Selector</label>
                <code class="mono">{{ selectedStep.target.selector || selectedStep.target.text || selectedStep.target.role || '—' }}</code>
              </div>
              <div class="detail-field full" *ngIf="selectedStep.value !== undefined">
                <label>Value</label>
                <input [(ngModel)]="selectedStep.value" />
              </div>
              <div class="detail-field full" *ngIf="selectedStep.params">
                <label>Parameters</label>
                <pre class="mono">{{ selectedStep.params | json }}</pre>
              </div>
            </div>
          </div>
        </div>

        <div class="empty-state" *ngIf="!steps.length && versions.length">
          <p>This version has no steps.</p>
          <a [routerLink]="['/processes', process.id, 'record']" class="btn-primary">Record a session</a>
        </div>
        <div class="empty-state" *ngIf="!versions.length">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><circle cx="12" cy="12" r="6"/><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
          <p>No versions yet. Record your first session to create one.</p>
          <a [routerLink]="['/processes', process.id, 'record']" class="btn-primary">Start Recording</a>
        </div>
      </div>

      <!-- Versions Tab -->
      <div class="tab-content" *ngIf="activeTab === 'versions'">
        <div class="card" style="padding:0; overflow:hidden;">
          <table>
            <thead>
              <tr><th>Version</th><th>Status</th><th>Steps</th><th>Created</th></tr>
            </thead>
            <tbody>
              <tr *ngFor="let v of versions">
                <td class="mono">v{{ v.version }}</td>
                <td><span class="badge" [ngClass]="v.status">{{ v.status }}</span></td>
                <td>{{ getStepCount(v) }}</td>
                <td class="mono text-muted">{{ v.created_at | date:'MMM d, HH:mm' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Executions Tab -->
      <div class="tab-content" *ngIf="activeTab === 'executions'">
        <div class="card" style="padding:0; overflow:hidden;">
          <table>
            <thead>
              <tr><th>ID</th><th>Status</th><th>Started</th><th>Completed</th><th>Actions</th></tr>
            </thead>
            <tbody>
              <tr *ngFor="let e of executions">
                <td class="mono">{{ e.id | slice:0:8 }}...</td>
                <td><span class="badge" [ngClass]="e.status">{{ e.status }}</span></td>
                <td class="mono text-muted">{{ e.started_at ? (e.started_at | date:'HH:mm:ss') : '—' }}</td>
                <td class="mono text-muted">{{ e.completed_at ? (e.completed_at | date:'HH:mm:ss') : '—' }}</td>
                <td><a [routerLink]="['/executions', e.id]" class="btn-ghost btn-sm">View</a></td>
              </tr>
              <tr *ngIf="!executions.length">
                <td colspan="5" class="empty-row">No executions yet. Run a version to create one.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Live Execution Panel -->
      <div class="live-panel" *ngIf="liveState">
        <div class="live-header">
          <h3>Live Execution</h3>
          <span class="badge" [ngClass]="liveState.status">{{ liveState.status }}</span>
        </div>
        <div class="live-progress">
          <div class="progress-bar">
            <div class="progress-fill" [style.width.%]="liveProgress"></div>
          </div>
          <span class="progress-text">{{ (liveState.completed_steps?.length || 0) }} / {{ steps.length }} steps</span>
        </div>
        <div class="live-error" *ngIf="liveState.error">{{ liveState.error }}</div>
      </div>
    </div>
  `,
  styles: [`
    .page { padding: 32px; max-width: 1200px; }

    .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-muted); }
    .breadcrumb a { color: var(--text-accent); }
    .breadcrumb span:last-child { color: var(--text-primary); }
    .top-actions { display: flex; gap: 8px; }
    .btn-with-icon { display: flex; align-items: center; gap: 6px; }

    .process-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
    .header-info { flex: 1; }
    .header-info h1 { margin-bottom: 4px; }
    .header-meta { display: flex; gap: 24px; }
    .meta-item { text-align: right; }
    .meta-label { display: block; font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: .05em; }
    .mono { font-family: var(--font-mono); font-size: 12px; }
    .text-muted { color: var(--text-muted); }

    .tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border-color); margin-bottom: 20px; }
    .tab {
      padding: 10px 20px;
      background: none;
      color: var(--text-secondary);
      border-bottom: 2px solid transparent;
      border-radius: 0;
      font-weight: 500;
    }
    .tab:hover { color: var(--text-primary); }
    .tab.active { color: var(--text-primary); border-bottom-color: var(--color-indigo); }

    .version-selector { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; font-size: 13px; }
    .version-selector label { color: var(--text-muted); }
    .version-selector select { min-width: 200px; }

    .steps-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .step-list { display: flex; flex-direction: column; gap: 4px; }
    .step-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      cursor: pointer;
      transition: all 0.15s;
    }
    .step-item:hover { border-color: var(--bg-tertiary); }
    .step-item.selected { border-color: var(--color-indigo); background: rgba(99,102,241,0.05); }
    .step-item.step-running { border-color: var(--color-blue); background: var(--color-blue-bg); }
    .step-item.step-done { border-left: 3px solid var(--color-green); }
    .step-item.step-failed { border-left: 3px solid var(--color-red); }
    .step-num { font-weight: 700; font-size: 12px; color: var(--text-muted); min-width: 20px; text-align: center; }
    .step-body { flex: 1; min-width: 0; }
    .step-type-badge { display: inline-block; font-size: 10px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-accent); background: rgba(99,102,241,0.1); padding: 1px 6px; border-radius: 3px; margin-bottom: 2px; }
    .step-label { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .step-status-dot { display: flex; align-items: center; }
    .dot-running { width: 8px; height: 8px; border-radius: 50%; background: var(--color-blue); animation: pulse 1s infinite; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

    .step-detail h3 { margin-bottom: 16px; }
    .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .detail-field { display: flex; flex-direction: column; gap: 4px; }
    .detail-field.full { grid-column: 1 / -1; }
    .detail-field label { font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: .05em; }
    .detail-field code, .detail-field pre { background: var(--bg-primary); padding: 8px 12px; border-radius: var(--radius-md); font-size: 12px; overflow-x: auto; white-space: pre-wrap; }

    .empty-state {
      padding: 64px 24px;
      text-align: center;
      color: var(--text-muted);
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
    }
    .empty-state svg { opacity: 0.3; }
    .empty-row { text-align: center; padding: 32px 12px !important; color: var(--text-muted); }

    .live-panel {
      margin-top: 20px;
      padding: 16px;
      background: var(--bg-surface);
      border: 1px solid var(--color-blue);
      border-radius: var(--radius-lg);
    }
    .live-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .live-progress { display: flex; align-items: center; gap: 12px; }
    .progress-bar { flex: 1; height: 6px; background: var(--bg-tertiary); border-radius: 3px; overflow: hidden; }
    .progress-fill { height: 100%; background: var(--color-indigo); border-radius: 3px; transition: width 0.3s; }
    .progress-text { font-size: 12px; color: var(--text-muted); min-width: 80px; text-align: right; }
    .live-error { margin-top: 8px; color: var(--color-red); font-size: 13px; padding: 8px; background: var(--color-red-bg); border-radius: var(--radius-md); }

    .btn-sm { padding: 4px 10px; font-size: 12px; }
  `]
})
export class ProcessEditorComponent implements OnInit, OnDestroy {
  process: Process | null = null;
  versions: ProcessVersion[] = [];
  executions: Execution[] = [];
  selectedVersionId = '';
  selectedStepIndex = -1;
  activeTab = 'steps';
  currentExecutionId: string | null = null;
  executionRunning = false;
  executionPaused = false;
  liveState: any = null;
  private ws: WebSocket | null = null;

  constructor(private api: ApiService, private route: ActivatedRoute, private router: Router) {}

  get selectedVersion(): ProcessVersion | undefined {
    return this.versions.find(v => v.id === this.selectedVersionId);
  }

  get steps(): ProcessStep[] {
    const def = this.selectedVersion?.definition;
    if (!def) return [];
    const proc = (def as any).process || def;
    return proc.steps || [];
  }

  get selectedStep(): ProcessStep | undefined {
    return this.selectedStepIndex >= 0 ? this.steps[this.selectedStepIndex] : undefined;
  }

  get liveProgress(): number {
    if (!this.liveState || !this.steps.length) return 0;
    return ((this.liveState.completed_steps?.length || 0) / this.steps.length) * 100;
  }

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id')!;
    if (id === 'new') {
      this.router.navigate(['/processes']);
      return;
    }
    this.api.getProcess(id).subscribe({
      next: p => this.process = p,
      error: () => this.router.navigate(['/processes'])
    });
    this.api.getVersions(id).subscribe(versions => {
      this.versions = versions;
      if (versions.length) this.selectedVersionId = versions[0].id;
    });
    this.api.getExecutions(id).subscribe({
      next: e => this.executions = e,
      error: () => this.executions = []
    });
  }

  onVersionChange() {
    this.selectedStepIndex = -1;
  }

  getStepCount(v: ProcessVersion): number {
    const proc = (v.definition as any)?.process || v.definition;
    return proc?.steps?.length || 0;
  }

  ngOnDestroy() {
    this.ws?.close();
  }

  runExecution() {
    if (!this.process || !this.selectedVersionId) return;
    this.api.createExecution(this.process.id, this.selectedVersionId).subscribe({
      next: exec => {
        this.currentExecutionId = exec.id;
        this.api.startExecution(exec.id).subscribe({
          next: () => {
            this.executionRunning = true;
            this.executionPaused = false;
            this.connectLive(exec.id);
          },
          error: () => {
            this.executionRunning = false;
          }
        });
      },
      error: () => {}
    });
  }

  pauseExecution() {
    if (!this.currentExecutionId) return;
    this.api.pauseExecution(this.currentExecutionId).subscribe(() => this.executionPaused = true);
  }

  resumeExecution() {
    if (!this.currentExecutionId) return;
    this.api.resumeExecution(this.currentExecutionId).subscribe(() => this.executionPaused = false);
  }

  cancelExecution() {
    if (!this.currentExecutionId) return;
    this.api.cancelExecution(this.currentExecutionId).subscribe(() => {
      this.executionRunning = false;
      this.executionPaused = false;
    });
  }

  private connectLive(executionId: string) {
    this.ws?.close();
    this.ws = this.api.connectExecutionWs(executionId);
    this.ws.onmessage = (event) => {
      const state = JSON.parse(event.data);
      this.liveState = state;
      this.executionPaused = state.paused || false;
      if (['succeeded', 'failed', 'cancelled'].includes(state.status)) {
        this.executionRunning = false;
        if (this.process) {
          this.api.getExecutions(this.process.id).subscribe(e => this.executions = e);
        }
      }
    };
    this.ws.onerror = () => this.executionRunning = false;
    this.ws.onclose = () => this.ws = null;
  }
}
