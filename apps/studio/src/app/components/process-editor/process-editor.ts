import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
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

      <!-- Header — editable -->
      <div class="process-header card">
        <div class="header-info">
          @if (editingHeader) {
            <input [(ngModel)]="editHeaderName" class="edit-name" placeholder="Process name" (keydown.enter)="saveHeader()" />
            <input [(ngModel)]="editHeaderDesc" class="edit-desc" placeholder="Description" (keydown.enter)="saveHeader()" />
            <div class="edit-actions">
              <button class="btn-primary btn-sm" (click)="saveHeader()">Save</button>
              <button class="btn-ghost btn-sm" (click)="editingHeader = false">Cancel</button>
            </div>
          } @else {
            <h1 (dblclick)="startEditHeader()">{{ process.name }}</h1>
            <span class="text-muted" (dblclick)="startEditHeader()">{{ process.description || 'No description — double-click to edit' }}</span>
            <button class="btn-ghost btn-sm edit-btn" (click)="startEditHeader()">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
              Edit
            </button>
          }
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
        <div class="version-bar" *ngIf="versions.length">
          <div class="version-selector">
            <label>Version:</label>
            <select [(ngModel)]="selectedVersionId" (ngModelChange)="onVersionChange()">
              <option *ngFor="let v of versions" [value]="v.id">v{{ v.version }} — {{ v.status }}</option>
            </select>
          </div>
          <div class="version-actions" *ngIf="selectedVersion">
            <button class="btn-ghost btn-sm" (click)="publishVersion()" *ngIf="selectedVersion.status === 'draft'">Publish</button>
            <button class="btn-primary btn-sm" (click)="saveSteps()" [disabled]="!dirty">Save Changes</button>
          </div>
        </div>

        <div class="steps-layout" *ngIf="steps.length">
          <div class="step-list">
            <div *ngFor="let step of steps; let i = index"
                 class="step-item"
                 [class.selected]="selectedStepIndex === i"
                 [class.step-running]="liveState && liveState.current_step_index === i"
                 [class.step-done]="liveState && (liveState.completed_steps || []).includes(step.id)"
                 [class.step-failed]="liveState && (liveState.failed_steps || []).includes(step.id)"
                 (click)="selectStep(i)">
              <span class="step-num">{{ i + 1 }}</span>
              <div class="step-body">
                <span class="step-type-badge">{{ step.type }}</span>
                <span class="step-label">{{ step.label || step.id }}</span>
              </div>
              <div class="step-actions-inline">
                <button class="btn-icon" (click)="moveStep(i, -1); $event.stopPropagation()" [disabled]="i === 0" title="Move up">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"/></svg>
                </button>
                <button class="btn-icon" (click)="moveStep(i, 1); $event.stopPropagation()" [disabled]="i === steps.length - 1" title="Move down">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
                <button class="btn-icon btn-icon-danger" (click)="deleteStep(i); $event.stopPropagation()" title="Delete step">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>
              <span class="step-status-dot" *ngIf="liveState">
                <span *ngIf="liveState.current_step_index === i" class="dot-running"></span>
                <svg *ngIf="(liveState.completed_steps || []).includes(step.id)" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-green)" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                <svg *ngIf="(liveState.failed_steps || []).includes(step.id)" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-red)" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </span>
            </div>
            <button class="btn-ghost add-step-btn" (click)="addStep()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Add Step
            </button>
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
                <select [(ngModel)]="selectedStep.type" (ngModelChange)="markDirty()">
                  <option value="browser.navigate">browser.navigate</option>
                  <option value="browser.wait">browser.wait</option>
                  <option value="ui.click">ui.click</option>
                  <option value="ui.dblclick">ui.dblclick</option>
                  <option value="ui.hover">ui.hover</option>
                  <option value="ui.fill">ui.fill</option>
                  <option value="ui.select">ui.select</option>
                  <option value="ui.scroll">ui.scroll</option>
                  <option value="keyboard.press">keyboard.press</option>
                  <option value="assertion">assertion</option>
                </select>
              </div>
              <div class="detail-field full">
                <label>Label</label>
                <input [(ngModel)]="selectedStep.label" (ngModelChange)="markDirty()" />
              </div>
              <div class="detail-field full" *ngIf="selectedStep.target">
                <label>Target Selector</label>
                <input [(ngModel)]="selectedStep.target.selector" (ngModelChange)="markDirty()" class="mono" />
              </div>
              <div class="detail-field" *ngIf="selectedStep.target">
                <label>Target Text</label>
                <input [(ngModel)]="selectedStep.target.text" (ngModelChange)="markDirty()" />
              </div>
              <div class="detail-field" *ngIf="selectedStep.target">
                <label>Target Role</label>
                <input [(ngModel)]="selectedStep.target.role" (ngModelChange)="markDirty()" />
              </div>
              <div class="detail-field full" *ngIf="selectedStep.value !== undefined">
                <label>Value</label>
                <input [(ngModel)]="selectedStep.value" (ngModelChange)="markDirty()" />
              </div>
              <div class="detail-field full" *ngIf="selectedStep.params">
                <label>Parameters (JSON)</label>
                <textarea [(ngModel)]="paramsJson" (ngModelChange)="onParamsJsonChange()" rows="4" class="mono"></textarea>
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
          <a [routerLink]="['/processes', process.id, 'record']" class="btn-primary">Record a session</a>
        </div>
      </div>

      <!-- Versions Tab -->
      <div class="tab-content" *ngIf="activeTab === 'versions'">
        <div class="card" style="padding:0; overflow:hidden;">
          <table>
            <thead>
              <tr><th>Version</th><th>Status</th><th>Steps</th><th>Created</th><th>Actions</th></tr>
            </thead>
            <tbody>
              <tr *ngFor="let v of versions">
                <td class="mono">v{{ v.version }}</td>
                <td><span class="badge" [ngClass]="v.status">{{ v.status }}</span></td>
                <td>{{ getStepCount(v) }}</td>
                <td class="mono text-muted">{{ v.created_at | date:'MMM d, HH:mm' }}</td>
                <td>
                  <div class="row-actions">
                    <button class="btn-ghost btn-sm" (click)="selectVersionTab(v)">View Steps</button>
                    <button class="btn-ghost btn-sm btn-delete" (click)="confirmDeleteVersion(v)">Delete</button>
                  </div>
                </td>
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

      @if (deleteVersionTarget) {
        <div class="modal-backdrop" (click)="deleteVersionTarget = null">
          <div class="modal" (click)="$event.stopPropagation()">
            <h3>Delete Version</h3>
            <p>Delete v{{ deleteVersionTarget.version }}? This cannot be undone.</p>
            @if (deleteVersionError) { <p style="color: var(--color-red); font-size: 13px">{{ deleteVersionError }}</p> }
            <div class="modal-actions">
              <button class="btn-danger" (click)="doDeleteVersion()">Delete</button>
              <button class="btn-secondary" (click)="deleteVersionTarget = null">Cancel</button>
            </div>
          </div>
        </div>
      }
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
    .header-info h1 { margin-bottom: 4px; cursor: pointer; }
    .edit-name { font-size: 18px; font-weight: 600; margin-bottom: 6px; width: 100%; }
    .edit-desc { font-size: 13px; width: 100%; margin-bottom: 8px; }
    .edit-actions { display: flex; gap: 6px; }
    .edit-btn { margin-top: 6px; display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--text-muted) !important; }
    .header-meta { display: flex; gap: 24px; }
    .meta-item { text-align: right; }
    .meta-label { display: block; font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: .05em; }
    .mono { font-family: var(--font-mono); font-size: 12px; }
    .text-muted { color: var(--text-muted); }
    .tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border-color); margin-bottom: 20px; }
    .tab { padding: 10px 20px; background: none; color: var(--text-secondary); border-bottom: 2px solid transparent; border-radius: 0; font-weight: 500; }
    .tab:hover { color: var(--text-primary); }
    .tab.active { color: var(--text-primary); border-bottom-color: var(--color-indigo); }
    .version-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .version-selector { display: flex; align-items: center; gap: 8px; font-size: 13px; }
    .version-selector label { color: var(--text-muted); }
    .version-selector select { min-width: 200px; }
    .version-actions { display: flex; gap: 8px; }
    .steps-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .step-list { display: flex; flex-direction: column; gap: 4px; }
    .step-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-md); cursor: pointer; transition: all 0.15s; }
    .step-item:hover { border-color: var(--bg-tertiary); }
    .step-item:hover .step-actions-inline { opacity: 1; }
    .step-item.selected { border-color: var(--color-indigo); background: rgba(99,102,241,0.05); }
    .step-item.step-running { border-color: var(--color-blue); background: var(--color-blue-bg); }
    .step-item.step-done { border-left: 3px solid var(--color-green); }
    .step-item.step-failed { border-left: 3px solid var(--color-red); }
    .step-num { font-weight: 700; font-size: 12px; color: var(--text-muted); min-width: 20px; text-align: center; }
    .step-body { flex: 1; min-width: 0; }
    .step-type-badge { display: inline-block; font-size: 10px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-accent); background: rgba(99,102,241,0.1); padding: 1px 6px; border-radius: 3px; margin-bottom: 2px; }
    .step-label { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .step-actions-inline { display: flex; gap: 2px; opacity: 0; transition: opacity 0.15s; }
    .btn-icon { background: none; border: none; padding: 3px; cursor: pointer; color: var(--text-muted); border-radius: 3px; display: flex; align-items: center; }
    .btn-icon:hover { background: var(--bg-hover); color: var(--text-primary); }
    .btn-icon:disabled { opacity: 0.3; cursor: not-allowed; }
    .btn-icon-danger:hover { background: var(--color-red-bg); color: var(--color-red); }
    .step-status-dot { display: flex; align-items: center; }
    .dot-running { width: 8px; height: 8px; border-radius: 50%; background: var(--color-blue); animation: pulse 1s infinite; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
    .add-step-btn { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 10px; border: 1px dashed var(--border-color); border-radius: var(--radius-md); color: var(--text-muted); font-size: 12px; }
    .add-step-btn:hover { border-color: var(--color-indigo); color: var(--text-primary); background: rgba(99,102,241,0.05); }
    .step-detail h3 { margin-bottom: 16px; }
    .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .detail-field { display: flex; flex-direction: column; gap: 4px; }
    .detail-field.full { grid-column: 1 / -1; }
    .detail-field label { font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: .05em; }
    .detail-field textarea { font-family: var(--font-mono); font-size: 12px; resize: vertical; min-height: 80px; }
    .btn-delete { color: var(--color-red) !important; }
    .btn-delete:hover { background: var(--color-red-bg) !important; }
    .row-actions { display: flex; gap: 4px; }
    .btn-sm { padding: 4px 10px; font-size: 12px; }
    .empty-state { padding: 64px 24px; text-align: center; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; gap: 12px; }
    .empty-state svg { opacity: 0.3; }
    .empty-row { text-align: center; padding: 32px 12px !important; color: var(--text-muted); }
    .live-panel { margin-top: 20px; padding: 16px; background: var(--bg-surface); border: 1px solid var(--color-blue); border-radius: var(--radius-lg); }
    .live-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .live-progress { display: flex; align-items: center; gap: 12px; }
    .progress-bar { flex: 1; height: 6px; background: var(--bg-tertiary); border-radius: 3px; overflow: hidden; }
    .progress-fill { height: 100%; background: var(--color-indigo); border-radius: 3px; transition: width 0.3s; }
    .progress-text { font-size: 12px; color: var(--text-muted); min-width: 80px; text-align: right; }
    .live-error { margin-top: 8px; color: var(--color-red); font-size: 13px; padding: 8px; background: var(--color-red-bg); border-radius: var(--radius-md); }
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.6); display: flex; align-items: center; justify-content: center; z-index: 1000; }
    .modal { background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 24px; max-width: 420px; width: 100%; }
    .modal h3 { margin-bottom: 12px; }
    .modal p { color: var(--text-secondary); font-size: 13px; margin-bottom: 20px; }
    .modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
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
  dirty = false;
  paramsJson = '';
  editingHeader = false;
  editHeaderName = '';
  editHeaderDesc = '';
  deleteVersionTarget: ProcessVersion | null = null;
  private pollTimer: any = null;

  constructor(private api: ApiService, private route: ActivatedRoute, private router: Router, private cdr: ChangeDetectorRef) {}

  get selectedVersion(): ProcessVersion | undefined { return this.versions.find(v => v.id === this.selectedVersionId); }
  get steps(): ProcessStep[] {
    const def = this.selectedVersion?.definition;
    if (!def) return [];
    return ((def as any).process || def).steps || [];
  }
  get selectedStep(): ProcessStep | undefined { return this.selectedStepIndex >= 0 ? this.steps[this.selectedStepIndex] : undefined; }
  get liveProgress(): number {
    if (!this.liveState || !this.steps.length) return 0;
    return ((this.liveState.completed_steps?.length || 0) / this.steps.length) * 100;
  }

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id')!;
    if (id === 'new') { this.router.navigate(['/processes']); return; }
    this.api.getProcess(id).subscribe({ next: p => { this.process = p; this.cdr.detectChanges(); }, error: () => this.router.navigate(['/processes']) });
    this.api.getVersions(id).subscribe(v => { this.versions = v; if (v.length) this.selectedVersionId = v[0].id; this.cdr.detectChanges(); });
    this.api.getExecutions(id).subscribe({ next: e => { this.executions = e; this.cdr.detectChanges(); }, error: () => { this.executions = []; this.cdr.detectChanges(); } });
  }

  onVersionChange() { this.selectedStepIndex = -1; this.dirty = false; }
  markDirty() { this.dirty = true; }

  selectStep(i: number) {
    this.selectedStepIndex = i;
    const step = this.selectedStep;
    this.paramsJson = step?.params ? JSON.stringify(step.params, null, 2) : '{}';
  }

  startEditHeader() {
    if (!this.process) return;
    this.editingHeader = true;
    this.editHeaderName = this.process.name;
    this.editHeaderDesc = this.process.description || '';
  }

  saveHeader() {
    if (!this.process || !this.editHeaderName.trim()) return;
    this.api.updateProcess(this.process.id, { name: this.editHeaderName.trim(), description: this.editHeaderDesc.trim() || undefined }).subscribe({
      next: p => { this.process = p; this.editingHeader = false; this.cdr.detectChanges(); },
      error: () => { this.editingHeader = false; this.cdr.detectChanges(); }
    });
  }

  saveSteps() {
    if (!this.process || !this.selectedVersion) return;
    const def = { ...this.selectedVersion.definition };
    ((def as any).process || def).steps = [...this.steps];
    this.api.updateVersion(this.process.id, this.selectedVersionId, { definition: def }).subscribe({
      next: v => { const idx = this.versions.findIndex(x => x.id === v.id); if (idx >= 0) this.versions[idx] = v; this.dirty = false; this.cdr.detectChanges(); }
    });
  }

  moveStep(index: number, direction: number) {
    const n = index + direction;
    if (n < 0 || n >= this.steps.length) return;
    const s = this.steps;
    [s[index], s[n]] = [s[n], s[index]];
    if (this.selectedStepIndex === index) this.selectedStepIndex = n;
    else if (this.selectedStepIndex === n) this.selectedStepIndex = index;
    this.markDirty();
    this.cdr.detectChanges();
  }

  deleteStep(index: number) {
    this.steps.splice(index, 1);
    if (this.selectedStepIndex >= this.steps.length) this.selectedStepIndex = this.steps.length - 1;
    this.markDirty();
    this.cdr.detectChanges();
  }

  addStep() {
    this.steps.push({ id: 'step-' + Math.random().toString(36).substring(2, 10), type: 'ui.click', label: 'New Step', target: { strategy: 'dom', selector: '' }, params: {} } as any);
    this.selectedStepIndex = this.steps.length - 1;
    this.paramsJson = '{}';
    this.markDirty();
    this.cdr.detectChanges();
  }

  onParamsJsonChange() { if (!this.selectedStep) return; try { this.selectedStep.params = JSON.parse(this.paramsJson); this.markDirty(); } catch {} }

  publishVersion() {
    if (!this.process || !this.selectedVersion) return;
    this.api.updateVersion(this.process.id, this.selectedVersionId, { status: 'published' }).subscribe({
      next: v => { const idx = this.versions.findIndex(x => x.id === v.id); if (idx >= 0) this.versions[idx] = v; this.cdr.detectChanges(); }
    });
  }

  selectVersionTab(v: ProcessVersion) { this.selectedVersionId = v.id; this.activeTab = 'steps'; this.selectedStepIndex = -1; this.dirty = false; this.cdr.detectChanges(); }
  deleteVersionError = '';
  confirmDeleteVersion(v: ProcessVersion) { this.deleteVersionTarget = v; this.deleteVersionError = ''; }
  doDeleteVersion() {
    if (!this.process || !this.deleteVersionTarget) return;
    this.deleteVersionError = '';
    this.api.deleteVersion(this.process.id, this.deleteVersionTarget.id).subscribe({
      next: () => { this.versions = this.versions.filter(v => v.id !== this.deleteVersionTarget!.id); if (this.selectedVersionId === this.deleteVersionTarget!.id) this.selectedVersionId = this.versions.length ? this.versions[0].id : ''; this.deleteVersionTarget = null; this.cdr.detectChanges(); },
      error: e => { this.deleteVersionError = e.error?.detail || 'Suppression impossible'; this.cdr.detectChanges(); }
    });
  }

  getStepCount(v: ProcessVersion): number { return ((v.definition as any)?.process || v.definition)?.steps?.length || 0; }
  ngOnDestroy() { if (this.pollTimer) clearInterval(this.pollTimer); }

  runExecution() {
    if (!this.process || !this.selectedVersionId) return;
    this.api.createExecution(this.process.id, this.selectedVersionId).subscribe({
      next: exec => { this.currentExecutionId = exec.id; this.api.startExecution(exec.id).subscribe({ next: () => { this.executionRunning = true; this.executionPaused = false; this.connectLive(exec.id); this.cdr.detectChanges(); }, error: () => { this.executionRunning = false; this.cdr.detectChanges(); } }); }
    });
  }

  pauseExecution() { if (this.currentExecutionId) this.api.pauseExecution(this.currentExecutionId).subscribe(() => { this.executionPaused = true; this.cdr.detectChanges(); }); }
  resumeExecution() { if (this.currentExecutionId) this.api.resumeExecution(this.currentExecutionId).subscribe(() => { this.executionPaused = false; this.cdr.detectChanges(); }); }
  cancelExecution() { if (this.currentExecutionId) this.api.cancelExecution(this.currentExecutionId).subscribe(() => { this.executionRunning = false; this.executionPaused = false; this.cdr.detectChanges(); }); }

  private connectLive(executionId: string) {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.pollTimer = setInterval(() => {
      this.api.getExecutionState(executionId).subscribe({
        next: (state: any) => {
          this.liveState = state; this.executionPaused = state.paused || false;
          if (['succeeded', 'failed', 'cancelled'].includes(state.status)) {
            this.executionRunning = false; clearInterval(this.pollTimer); this.pollTimer = null;
            if (this.process) this.api.getExecutions(this.process.id).subscribe(e => { this.executions = e; this.cdr.detectChanges(); });
          }
          this.cdr.detectChanges();
        },
        error: () => { this.executionRunning = false; clearInterval(this.pollTimer); this.pollTimer = null; this.cdr.detectChanges(); }
      });
    }, 500);
  }
}
