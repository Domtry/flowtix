import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { Process, ProcessVersion, ProcessStep } from '../../models/process.model';

@Component({
  selector: 'app-process-editor',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <div class="editor" *ngIf="process">
      <header>
        <div>
          <h1>{{ process.name }}</h1>
          <p class="subtitle">{{ process.description || 'No description' }}</p>
        </div>
        <div class="actions">
          <button class="btn" [routerLink]="['/processes', process.id, 'record']">Record</button>
          <button class="btn-primary" (click)="runExecution()" [disabled]="!selectedVersion">Run</button>
        </div>
      </header>

      <div class="version-bar">
        <label>Version:</label>
        <select [(ngModel)]="selectedVersionId" (ngModelChange)="onVersionChange()">
          <option *ngFor="let v of versions" [value]="v.id">v{{ v.version }} ({{ v.status }})</option>
        </select>
      </div>

      <div class="steps-panel" *ngIf="steps.length">
        <h2>Steps ({{ steps.length }})</h2>
        <div class="step-list">
          <div *ngFor="let step of steps; let i = index" class="step-card" [class.selected]="selectedStepIndex === i" (click)="selectedStepIndex = i">
            <span class="step-number">{{ i + 1 }}</span>
            <div class="step-info">
              <span class="step-type">{{ step.type }}</span>
              <span class="step-label">{{ step.label || step.id }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="step-detail" *ngIf="selectedStep">
        <h3>Step Detail</h3>
        <div class="detail-row"><label>ID:</label> <span>{{ selectedStep.id }}</span></div>
        <div class="detail-row"><label>Type:</label> <span>{{ selectedStep.type }}</span></div>
        <div class="detail-row"><label>Label:</label> <input [(ngModel)]="selectedStep.label" /></div>
        <div class="detail-row" *ngIf="selectedStep.target">
          <label>Target:</label>
          <code>{{ selectedStep.target.selector || selectedStep.target.text || selectedStep.target.role }}</code>
        </div>
        <div class="detail-row" *ngIf="selectedStep.value !== undefined">
          <label>Value:</label> <input [(ngModel)]="selectedStep.value" />
        </div>
        <div class="detail-row" *ngIf="selectedStep.params">
          <label>Params:</label>
          <pre>{{ selectedStep.params | json }}</pre>
        </div>
      </div>

      <div class="empty-state" *ngIf="!steps.length && versions.length">
        <p>This version has no steps. <a [routerLink]="['/processes', process.id, 'record']">Record a session</a> to generate steps.</p>
      </div>

      <div class="empty-state" *ngIf="!versions.length">
        <p>No versions yet. <a [routerLink]="['/processes', process.id, 'record']">Record your first session</a>.</p>
      </div>
    </div>
  `,
  styles: [`
    .editor { padding: 24px; max-width: 1200px; margin: 0 auto; }
    header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
    .subtitle { color: #64748b; margin: 4px 0 0; }
    .actions { display: flex; gap: 8px; }
    .btn { background: #e2e8f0; color: #1e293b; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
    .btn-primary { background: #4f46e5; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
    .btn-primary:disabled { opacity: .5; cursor: not-allowed; }
    .version-bar { margin-bottom: 24px; display: flex; align-items: center; gap: 8px; }
    .version-bar select { padding: 6px 12px; border: 1px solid #e2e8f0; border-radius: 4px; }
    .steps-panel h2 { margin-bottom: 12px; }
    .step-list { display: flex; flex-direction: column; gap: 4px; }
    .step-card { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; cursor: pointer; }
    .step-card.selected { border-color: #4f46e5; background: #eef2ff; }
    .step-number { font-weight: 700; color: #4f46e5; min-width: 24px; }
    .step-type { font-size: 11px; text-transform: uppercase; color: #64748b; }
    .step-label { display: block; }
    .step-detail { margin-top: 24px; padding: 16px; background: #f8fafc; border-radius: 8px; }
    .detail-row { margin-bottom: 8px; display: flex; gap: 8px; align-items: center; }
    .detail-row label { font-weight: 600; min-width: 80px; color: #475569; }
    .detail-row input { padding: 4px 8px; border: 1px solid #e2e8f0; border-radius: 4px; flex: 1; }
    .detail-row code, .detail-row pre { background: #e2e8f0; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
    .empty-state { color: #64748b; margin-top: 32px; }
    .empty-state a { color: #4f46e5; }
  `]
})
export class ProcessEditorComponent implements OnInit {
  process: Process | null = null;
  versions: ProcessVersion[] = [];
  selectedVersionId = '';
  selectedStepIndex = -1;

  constructor(private api: ApiService, private route: ActivatedRoute) {}

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

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.api.getProcess(id).subscribe(p => this.process = p);
    this.api.getVersions(id).subscribe(versions => {
      this.versions = versions;
      if (versions.length) {
        this.selectedVersionId = versions[0].id;
      }
    });
  }

  onVersionChange() {
    this.selectedStepIndex = -1;
  }

  runExecution() {
    if (!this.process || !this.selectedVersionId) return;
    this.api.createExecution(this.process.id, this.selectedVersionId).subscribe(exec => {
      alert(`Execution created: ${exec.id} (status: ${exec.status})`);
    });
  }
}
