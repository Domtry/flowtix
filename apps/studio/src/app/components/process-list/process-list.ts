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
      <header>
        <h1>Processes</h1>
        <button class="btn-primary" (click)="showCreate = true">+ New Process</button>
      </header>

      @if (showCreate) {
        <div class="create-form">
          <input [(ngModel)]="newName" placeholder="Process name" />
          <input [(ngModel)]="newDesc" placeholder="Description (optional)" />
          <button class="btn-primary" (click)="create()">Create</button>
          <button class="btn-secondary" (click)="showCreate = false">Cancel</button>
        </div>
      }

      <table class="process-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Description</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          @for (p of processes; track p.id) {
            <tr>
              <td><a [routerLink]="['/processes', p.id]">{{ p.name }}</a></td>
              <td>{{ p.description || '—' }}</td>
              <td>{{ p.created_at | date:'short' }}</td>
              <td>
                <a [routerLink]="['/processes', p.id, 'edit']" class="action-link">Edit</a>
                <a [routerLink]="['/processes', p.id, 'record']" class="action-link">Record</a>
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
  styles: [`
    .page { padding: 24px; max-width: 1200px; margin: 0 auto; }
    header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
    .btn-primary { background: #4f46e5; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
    .btn-secondary { background: #e2e8f0; color: #1e293b; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
    .create-form { display: flex; gap: 8px; margin-bottom: 24px; padding: 16px; background: #f8fafc; border-radius: 8px; }
    .create-form input { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 4px; flex: 1; }
    .process-table { width: 100%; border-collapse: collapse; }
    .process-table th, .process-table td { text-align: left; padding: 12px; border-bottom: 1px solid #e2e8f0; }
    .process-table th { color: #64748b; font-size: 12px; text-transform: uppercase; }
    .process-table a { color: #4f46e5; text-decoration: none; }
    .action-link { margin-right: 12px; font-size: 13px; }
  `]
})
export class ProcessListComponent implements OnInit {
  processes: Process[] = [];
  showCreate = false;
  newName = '';
  newDesc = '';

  constructor(private api: ApiService) {}

  ngOnInit() {
    this.loadProcesses();
  }

  loadProcesses() {
    this.api.getProcesses().subscribe(p => this.processes = p);
  }

  create() {
    if (!this.newName.trim()) return;
    this.api.createProcess(this.newName, this.newDesc || undefined).subscribe(() => {
      this.showCreate = false;
      this.newName = '';
      this.newDesc = '';
      this.loadProcesses();
    });
  }
}
