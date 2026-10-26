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
    <div class="execution-page" *ngIf="execution">
      <header>
        <h1>Execution</h1>
        <span class="status-badge" [class]="execution.status">{{ execution.status }}</span>
      </header>

      <div class="meta-grid">
        <div class="meta-item"><label>ID</label><span>{{ execution.id }}</span></div>
        <div class="meta-item"><label>Started</label><span>{{ execution.started_at | date:'medium' }}</span></div>
        <div class="meta-item"><label>Completed</label><span>{{ execution.completed_at | date:'medium' }}</span></div>
        <div class="meta-item"><label>Current Step</label><span>{{ execution.current_step_id || '—' }}</span></div>
      </div>

      <div class="steps-section" *ngIf="steps.length">
        <h2>Steps</h2>
        <div *ngFor="let step of steps" class="step-row" [class]="step.status">
          <span class="step-index">{{ step.step_index + 1 }}</span>
          <span class="step-id">{{ step.step_id }}</span>
          <span class="step-status">{{ step.status }}</span>
          <span class="step-duration" *ngIf="step.started_at && step.completed_at">
            {{ getDuration(step) }}ms
          </span>
          <span class="step-error" *ngIf="step.error">{{ step.error | json }}</span>
        </div>
      </div>

      <div class="error-section" *ngIf="execution.error">
        <h2>Error</h2>
        <pre>{{ execution.error | json }}</pre>
      </div>

      <div class="outputs-section" *ngIf="execution.outputs">
        <h2>Outputs</h2>
        <pre>{{ execution.outputs | json }}</pre>
      </div>
    </div>
  `,
  styles: [`
    .execution-page { padding: 24px; max-width: 1000px; margin: 0 auto; }
    header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
    .status-badge { padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: 600; text-transform: uppercase; }
    .status-badge.created { background: #e2e8f0; color: #475569; }
    .status-badge.running { background: #dbeafe; color: #1d4ed8; }
    .status-badge.succeeded { background: #dcfce7; color: #166534; }
    .status-badge.failed { background: #fee2e2; color: #991b1b; }
    .status-badge.paused { background: #fef3c7; color: #92400e; }
    .meta-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 24px; }
    .meta-item { background: #f8fafc; padding: 12px; border-radius: 6px; }
    .meta-item label { display: block; font-size: 11px; text-transform: uppercase; color: #64748b; margin-bottom: 4px; }
    .steps-section { margin-bottom: 24px; }
    .step-row { display: flex; gap: 12px; padding: 8px 12px; border-bottom: 1px solid #f1f5f9; align-items: center; }
    .step-row.succeeded { border-left: 3px solid #22c55e; }
    .step-row.failed { border-left: 3px solid #ef4444; }
    .step-row.pending { border-left: 3px solid #e2e8f0; }
    .step-index { font-weight: 700; color: #64748b; min-width: 24px; }
    .step-id { flex: 1; }
    .step-status { font-size: 12px; text-transform: uppercase; }
    .step-duration { color: #64748b; font-size: 12px; }
    .step-error { color: #ef4444; font-size: 12px; }
    .error-section pre, .outputs-section pre { background: #f8fafc; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 13px; }
  `]
})
export class ExecutionViewComponent implements OnInit {
  execution: Execution | null = null;
  steps: ExecutionStep[] = [];

  constructor(private api: ApiService, private route: ActivatedRoute) {}

  ngOnInit() {
    const execId = this.route.snapshot.paramMap.get('executionId')!;
    this.api.getExecution(execId).subscribe(e => this.execution = e);
    this.api.getExecutionSteps(execId).subscribe(s => this.steps = s);
  }

  getDuration(step: ExecutionStep): number {
    if (!step.started_at || !step.completed_at) return 0;
    return new Date(step.completed_at).getTime() - new Date(step.started_at).getTime();
  }
}
