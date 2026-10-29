import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { Process } from '../../models/process.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="page">
      <div class="page-header">
        <div>
          <h1>Dashboard</h1>
          <p class="subtitle">Overview of your RPA processes</p>
        </div>
        <button class="btn-primary" routerLink="/processes">View All Processes</button>
      </div>

      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <div>
            <span class="stat-value">{{ processes.length }}</span>
            <span class="stat-label">Processes</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon green">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <div>
            <span class="stat-value">{{ recentCount }}</span>
            <span class="stat-label">Recent (7d)</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon indigo">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </div>
          <div>
            <span class="stat-value">0</span>
            <span class="stat-label">Running</span>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-header">
          <h2>Recent Processes</h2>
        </div>
        @if (processes.length) {
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              @for (p of processes; track p.id) {
                <tr>
                  <td><a [routerLink]="['/processes', p.id]" class="process-name">{{ p.name }}</a></td>
                  <td class="text-secondary">{{ p.description || '—' }}</td>
                  <td class="text-muted mono">{{ p.updated_at | date:'MMM d, HH:mm' }}</td>
                  <td>
                    <div class="actions">
                      <a [routerLink]="['/processes', p.id]" class="btn-ghost btn-sm">Open</a>
                      <a [routerLink]="['/processes', p.id, 'record']" class="btn-ghost btn-sm">Record</a>
                    </div>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        } @else {
          <div class="empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <p>No processes yet</p>
            <a routerLink="/processes" class="btn-primary">Create your first process</a>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .page { padding: 32px; max-width: 1200px; }
    .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 28px; }
    .subtitle { color: var(--text-muted); font-size: 13px; margin-top: 4px; }

    .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }
    .stat-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-lg);
      padding: 20px;
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .stat-icon {
      width: 40px; height: 40px;
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .stat-icon.blue { background: var(--color-blue-bg); color: var(--color-blue); }
    .stat-icon.green { background: var(--color-green-bg); color: var(--color-green); }
    .stat-icon.indigo { background: rgba(99,102,241,.1); color: var(--color-indigo); }
    .stat-value { display: block; font-size: 24px; font-weight: 700; }
    .stat-label { color: var(--text-muted); font-size: 12px; }

    .section { background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-lg); overflow: hidden; }
    .section-header { padding: 16px 20px; border-bottom: 1px solid var(--border-color); }

    .process-name { font-weight: 500; }
    .text-secondary { color: var(--text-secondary); }
    .text-muted { color: var(--text-muted); }
    .mono { font-family: var(--font-mono); font-size: 12px; }

    .actions { display: flex; gap: 4px; }
    .btn-sm { padding: 4px 10px; font-size: 12px; }

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
    .empty-state p { font-size: 15px; }
  `]
})
export class DashboardComponent implements OnInit {
  processes: Process[] = [];

  get recentCount(): number {
    const week = Date.now() - 7 * 86400000;
    return this.processes.filter(p => new Date(p.updated_at).getTime() > week).length;
  }

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit() {
    this.api.getProcesses().subscribe({
      next: p => { this.processes = p; this.cdr.detectChanges(); },
      error: () => { this.processes = []; this.cdr.detectChanges(); }
    });
  }
}
