import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { Process } from '../../models/process.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="dashboard">
      <header class="dashboard-header">
        <h1>FlowtTix Studio</h1>
        <button class="btn-primary" routerLink="/processes/new">+ New Process</button>
      </header>

      <section class="stats">
        <div class="stat-card">
          <span class="stat-value">{{ processes.length }}</span>
          <span class="stat-label">Processes</span>
        </div>
      </section>

      <section class="recent">
        <h2>Recent Processes</h2>
        <div class="process-grid">
          @for (p of processes; track p.id) {
            <a class="process-card" [routerLink]="['/processes', p.id]">
              <h3>{{ p.name }}</h3>
              <p>{{ p.description || 'No description' }}</p>
              <time>{{ p.updated_at | date:'short' }}</time>
            </a>
          }
          @empty {
            <p class="empty">No processes yet. Create one to get started.</p>
          }
        </div>
      </section>
    </div>
  `,
  styles: [`
    .dashboard { padding: 24px; max-width: 1200px; margin: 0 auto; }
    .dashboard-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
    .btn-primary { background: #4f46e5; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; }
    .btn-primary:hover { background: #4338ca; }
    .stats { display: flex; gap: 16px; margin-bottom: 32px; }
    .stat-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; min-width: 150px; }
    .stat-value { display: block; font-size: 32px; font-weight: 700; color: #1e293b; }
    .stat-label { color: #64748b; font-size: 14px; }
    .process-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
    .process-card { display: block; background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; text-decoration: none; color: inherit; transition: box-shadow .15s; }
    .process-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,.08); }
    .process-card h3 { margin: 0 0 8px; color: #1e293b; }
    .process-card p { margin: 0 0 8px; color: #64748b; font-size: 14px; }
    .process-card time { color: #94a3b8; font-size: 12px; }
    .empty { color: #94a3b8; }
  `]
})
export class DashboardComponent implements OnInit {
  processes: Process[] = [];

  constructor(private api: ApiService) {}

  ngOnInit() {
    this.api.getProcesses().subscribe(p => this.processes = p);
  }
}
