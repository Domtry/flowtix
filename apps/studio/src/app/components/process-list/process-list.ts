import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { Process } from '../../models/process.model';

@Component({
  selector: 'app-process-list',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <div class="page">
      <div class="page-header">
        <div>
          <h1>Processes</h1>
          <p class="subtitle">Manage your RPA process definitions</p>
        </div>
        <button class="btn-primary" (click)="showCreate = !showCreate">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New Process
        </button>
      </div>

      @if (showCreate) {
        <div class="create-panel card">
          <h3>Create Process</h3>
          <div class="form-row">
            <div class="form-group">
              <label>Name</label>
              <input [(ngModel)]="newName" placeholder="e.g. Invoice Processing" (keydown.enter)="create()" />
            </div>
            <div class="form-group">
              <label>Robot</label>
              <select [(ngModel)]="newRobotCode">
                <option value="">— Aucun —</option>
                @for (r of robots; track r.code) {
                  <option [value]="r.code">{{ r.name }} ({{ r.code }})</option>
                }
              </select>
            </div>
          </div>
          <div class="form-row" style="margin-top: 8px;">
            <div class="form-group">
              <label>Description</label>
              <input [(ngModel)]="newDesc" placeholder="Optional description" (keydown.enter)="create()" />
            </div>
            <div class="form-actions">
              <button class="btn-primary" (click)="create()" [disabled]="!newName.trim()">Create</button>
              <button class="btn-secondary" (click)="showCreate = false">Cancel</button>
            </div>
          </div>
          @if (createError) {
            <p class="error-msg">{{ createError }}</p>
          }
        </div>
      }

      <div class="table-container card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Robot</th>
              <th>Description</th>
              <th>Created</th>
              <th style="width: 240px">Actions</th>
            </tr>
          </thead>
          <tbody>
            @for (p of processes; track p.id) {
              <tr>
                <td>
                  @if (editingId === p.id) {
                    <input [(ngModel)]="editName" class="inline-edit" (keydown.enter)="saveEdit(p)" (keydown.escape)="cancelEdit()" />
                  } @else {
                    <a [routerLink]="['/processes', p.id]" class="name-link">{{ p.name }}</a>
                  }
                </td>
                <td>
                  @if (p.robot_code) {
                    <span class="robot-badge">{{ p.robot_code }}</span>
                  } @else {
                    <span class="text-muted">—</span>
                  }
                </td>
                <td class="text-secondary">
                  @if (editingId === p.id) {
                    <input [(ngModel)]="editDesc" class="inline-edit" placeholder="Description" (keydown.enter)="saveEdit(p)" (keydown.escape)="cancelEdit()" />
                  } @else {
                    {{ p.description || '—' }}
                  }
                </td>
                <td class="mono text-muted">{{ p.created_at | date:'MMM d, yyyy' }}</td>
                <td>
                  <div class="row-actions">
                    @if (editingId === p.id) {
                      <button class="btn-primary btn-sm" (click)="saveEdit(p)">Save</button>
                      <button class="btn-ghost btn-sm" (click)="cancelEdit()">Cancel</button>
                    } @else {
                      <a [routerLink]="['/processes', p.id]" class="btn-ghost btn-sm">Open</a>
                      <button class="btn-ghost btn-sm" (click)="startEdit(p)">Edit</button>
                      <a [routerLink]="['/processes', p.id, 'record']" class="btn-ghost btn-sm">Record</a>
                      <button class="btn-ghost btn-sm btn-delete" (click)="confirmDelete(p)">Delete</button>
                    }
                  </div>
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="5" class="empty-row">No processes found. Create one to get started.</td>
              </tr>
            }
          </tbody>
        </table>
      </div>

      @if (deleteTarget) {
        <div class="modal-backdrop" (click)="deleteTarget = null">
          <div class="modal" (click)="$event.stopPropagation()">
            <h3>Delete Process</h3>
            <p>Are you sure you want to delete <strong>{{ deleteTarget.name }}</strong>? This will remove all versions and executions.</p>
            @if (deleteError) { <p class="error-msg">{{ deleteError }}</p> }
            <div class="modal-actions">
              <button class="btn-danger" (click)="doDelete()">Delete</button>
              <button class="btn-secondary" (click)="deleteTarget = null">Cancel</button>
            </div>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .page { padding: 32px; max-width: 1200px; }
    .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
    .page-header .btn-primary { display: flex; align-items: center; gap: 6px; }
    .subtitle { color: var(--text-muted); font-size: 13px; margin-top: 4px; }

    .create-panel { margin-bottom: 20px; }
    .create-panel h3 { margin-bottom: 12px; }
    .form-row { display: flex; gap: 12px; align-items: flex-end; }
    .form-group { flex: 1; }
    .form-group label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; text-transform: uppercase; letter-spacing: .05em; }
    .form-group input { width: 100%; }
    .form-actions { display: flex; gap: 8px; }
    .error-msg { color: var(--color-red); font-size: 13px; margin-top: 8px; }

    .table-container { padding: 0; overflow: hidden; }
    .name-link { font-weight: 500; }
    .text-secondary { color: var(--text-secondary); }
    .text-muted { color: var(--text-muted); }
    .mono { font-family: var(--font-mono); font-size: 12px; }

    .inline-edit { width: 100%; font-size: 13px; padding: 4px 8px; }

    .row-actions { display: flex; gap: 4px; }
    .btn-sm { padding: 4px 10px; font-size: 12px; }
    .btn-delete { color: var(--color-red) !important; }
    .btn-delete:hover { background: var(--color-red-bg) !important; }

    .robot-badge { font-family: var(--font-mono); font-size: 10px; padding: 2px 8px; border-radius: 10px; background: var(--color-indigo-bg, rgba(99,102,241,0.1)); color: var(--color-indigo); font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
    .empty-row { text-align: center; padding: 48px 24px !important; color: var(--text-muted); }

    .modal-backdrop {
      position: fixed; inset: 0; background: rgba(0,0,0,.6);
      display: flex; align-items: center; justify-content: center; z-index: 1000;
    }
    .modal {
      background: var(--bg-surface); border: 1px solid var(--border-color);
      border-radius: var(--radius-lg); padding: 24px; max-width: 420px; width: 100%;
    }
    .modal h3 { margin-bottom: 12px; }
    .modal p { color: var(--text-secondary); font-size: 13px; margin-bottom: 20px; line-height: 1.6; }
    .modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
  `]
})
export class ProcessListComponent implements OnInit {
  processes: Process[] = [];
  robots: any[] = [];
  showCreate = false;
  newName = '';
  newDesc = '';
  newRobotCode = '';
  createError = '';
  editingId: string | null = null;
  editName = '';
  editDesc = '';
  deleteTarget: Process | null = null;
  deleteError = '';

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit() {
    this.loadProcesses();
    this.api.getRobots().subscribe({ next: r => { this.robots = r; this.cdr.detectChanges(); } });
  }

  loadProcesses() {
    this.api.getProcesses().subscribe({
      next: p => { this.processes = p; this.cdr.detectChanges(); },
      error: () => { this.processes = []; this.cdr.detectChanges(); }
    });
  }

  create() {
    if (!this.newName.trim()) return;
    this.createError = '';
    this.api.createProcess(this.newName.trim(), this.newDesc.trim() || undefined, this.newRobotCode || undefined).subscribe({
      next: () => {
        this.showCreate = false;
        this.newName = '';
        this.newDesc = '';
        this.newRobotCode = '';
        this.loadProcesses();
        this.cdr.detectChanges();
      },
      error: err => {
        this.createError = err.error?.detail || 'Failed to create process';
        this.cdr.detectChanges();
      }
    });
  }

  startEdit(p: Process) {
    this.editingId = p.id;
    this.editName = p.name;
    this.editDesc = p.description || '';
  }

  cancelEdit() {
    this.editingId = null;
  }

  saveEdit(p: Process) {
    if (!this.editName.trim()) return;
    this.api.updateProcess(p.id, { name: this.editName.trim(), description: this.editDesc.trim() || undefined }).subscribe({
      next: () => {
        this.editingId = null;
        this.loadProcesses();
      },
      error: () => { this.editingId = null; }
    });
  }

  confirmDelete(p: Process) {
    this.deleteTarget = p;
    this.deleteError = '';
  }

  doDelete() {
    if (!this.deleteTarget) return;
    this.deleteError = '';
    this.api.deleteProcess(this.deleteTarget.id).subscribe({
      next: () => {
        this.deleteTarget = null;
        this.loadProcesses();
      },
      // keep the dialog open with the reason (e.g. used by a workflow)
      error: e => { this.deleteError = e.error?.detail || 'Suppression impossible'; this.cdr.detectChanges(); }
    });
  }
}
