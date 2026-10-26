import { Component, OnInit } from '@angular/core';
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
              <th>Description</th>
              <th>Created</th>
              <th>Updated</th>
              <th style="width: 180px">Actions</th>
            </tr>
          </thead>
          <tbody>
            @for (p of processes; track p.id) {
              <tr>
                <td>
                  <a [routerLink]="['/processes', p.id]" class="name-link">{{ p.name }}</a>
                </td>
                <td class="text-secondary">{{ p.description || '—' }}</td>
                <td class="mono text-muted">{{ p.created_at | date:'MMM d, yyyy' }}</td>
                <td class="mono text-muted">{{ p.updated_at | date:'MMM d, HH:mm' }}</td>
                <td>
                  <div class="row-actions">
                    <a [routerLink]="['/processes', p.id]" class="btn-ghost btn-sm">Open</a>
                    <a [routerLink]="['/processes', p.id, 'edit']" class="btn-ghost btn-sm">Edit</a>
                    <a [routerLink]="['/processes', p.id, 'record']" class="btn-ghost btn-sm">Record</a>
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

    .row-actions { display: flex; gap: 4px; }
    .btn-sm { padding: 4px 10px; font-size: 12px; }

    .empty-row { text-align: center; padding: 48px 24px !important; color: var(--text-muted); }
  `]
})
export class ProcessListComponent implements OnInit {
  processes: Process[] = [];
  showCreate = false;
  newName = '';
  newDesc = '';
  createError = '';

  constructor(private api: ApiService) {}

  ngOnInit() {
    this.loadProcesses();
  }

  loadProcesses() {
    this.api.getProcesses().subscribe({
      next: p => this.processes = p,
      error: () => this.processes = []
    });
  }

  create() {
    if (!this.newName.trim()) return;
    this.createError = '';
    this.api.createProcess(this.newName.trim(), this.newDesc.trim() || undefined).subscribe({
      next: () => {
        this.showCreate = false;
        this.newName = '';
        this.newDesc = '';
        this.loadProcesses();
      },
      error: err => {
        this.createError = err.error?.detail || 'Failed to create process';
      }
    });
  }
}
