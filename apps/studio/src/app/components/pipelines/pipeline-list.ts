import { Component, OnDestroy, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { RUN_STATUS_LABELS, TRIGGER_LABELS } from './pipeline-labels';

@Component({
  selector: 'app-pipeline-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="page">
      <div class="header-row">
        <div>
          <h1>Workflows</h1>
          <p class="subtitle">Enchaînez robots, conditions, boucles, données et intégrations — déclenchés à la main, selon un planning ou par API.</p>
        </div>
        @if (!showCreate) {
          <button class="btn-primary" (click)="showCreate = true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Nouveau workflow
          </button>
        }
      </div>

      @if (error) { <div class="error-banner">{{ error }}</div> }

      @if (showCreate) {
        <div class="card form-card">
          <h3>Nouveau workflow</h3>
          <div class="form-grid">
            <div class="form-field">
              <label>Nom</label>
              <input [(ngModel)]="form.name" placeholder="Saisie des contrats du jour" (keyup.enter)="form.name && create()" />
            </div>
            <div class="form-field">
              <label>Robot</label>
              <select [(ngModel)]="form.robot_code">
                <option value="">— Choisir —</option>
                @for (r of robots; track r.code) { <option [value]="r.code">{{ r.code }} — {{ r.name }}</option> }
              </select>
              <span class="hint">La plateforme pilotée : tous les processus du workflow sont exécutés par ce robot.</span>
            </div>
          </div>
          <div class="form-field">
            <label>Description (facultatif)</label>
            <input [(ngModel)]="form.description" placeholder="Saisie des contrats Santé selon l'option choisie" />
          </div>
          <div class="form-actions">
            <button class="btn-primary" (click)="create()" [disabled]="!form.name || !form.robot_code || saving">Créer et ouvrir l'éditeur</button>
            <button class="btn-ghost" (click)="showCreate = false">Annuler</button>
          </div>
        </div>
      }

      @if (pipelines.length) {
        <div class="card table-card">
          <table>
            <thead>
              <tr><th>Workflow</th><th>Robot</th><th>Déclencheurs</th><th>Blocs</th><th>Prochain lancement</th><th>Dernier run</th><th></th></tr>
            </thead>
            <tbody>
              @for (p of pipelines; track p.id) {
                <tr (click)="open(p.id)">
                  <td>
                    <div class="name">{{ p.name }}</div>
                    @if (p.description) { <div class="muted">{{ p.description }}</div> }
                  </td>
                  <td>
                    @if (p.robot_code) {
                      <span class="robot">{{ p.robot_code }}</span>
                      @if (p.robot_name) { <div class="muted">{{ p.robot_name }}</div> }
                    } @else { <span class="missing">à choisir</span> }
                  </td>
                  <td>
                    @for (t of p.triggers; track t) { <span class="chip">{{ triggerName(t) }}</span> }
                  </td>
                  <td class="muted">{{ p.node_count }}</td>
                  <td>
                    @if (p.next_run_at) { {{ p.next_run_at | date:'EEE dd/MM HH:mm':'UTC' }} }
                    @else { <span class="muted">—</span> }
                  </td>
                  <td>
                    @if (p.last_run) {
                      <span class="status" [attr.data-status]="p.last_run.status">{{ statusLabel(p.last_run.status) }}</span>
                      <div class="muted">{{ p.last_run.succeeded }}/{{ p.last_run.total_rows }} ok · {{ triggerLabel(p.last_run.trigger) }}</div>
                    } @else { <span class="muted">Jamais lancé</span> }
                  </td>
                  <td class="actions">
                    <button class="del" title="Supprimer ce workflow" (click)="$event.stopPropagation(); remove(p)">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                    </button>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      } @else if (!showCreate && loaded) {
        <div class="card empty-state">
          <h3>Aucun workflow</h3>
          <p>Un workflow relie des blocs : déclencheur → lecture d'un fichier → condition → robot → e-mail de compte rendu…</p>
          <button class="btn-primary" (click)="showCreate = true">Créer un workflow</button>
        </div>
      }
    </div>
  `,
  styles: [`
    .page { padding: 32px; max-width: 1100px; }
    .header-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
    .subtitle { color: var(--text-muted); font-size: 13px; margin: 4px 0 0; }
    .error-banner { padding: 10px 14px; background: var(--color-red-bg); color: var(--color-red); border-radius: var(--radius-md); margin-bottom: 16px; font-size: 13px; }
    .form-card { margin-bottom: 24px; }
    .form-card h3 { margin-bottom: 16px; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .form-field { margin-bottom: 14px; }
    .form-field > label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); margin-bottom: 4px; font-weight: 600; }
    .form-field input:not([type=radio]), .form-field select { width: 100%; }
    .radio-row { display: flex; gap: 20px; font-size: 13px; }
    .radio { display: flex; align-items: center; gap: 6px; cursor: pointer; }
    .form-actions { display: flex; gap: 10px; }
    .table-card { padding: 0; overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); padding: 12px 16px; border-bottom: 1px solid var(--border-color); font-weight: 600; }
    td { padding: 12px 16px; border-bottom: 1px solid var(--border-color); vertical-align: top; }
    tbody tr { cursor: pointer; }
    tbody tr:hover { background: var(--bg-hover); }
    tbody tr:last-child td { border-bottom: none; }
    .name { font-weight: 600; }
    .actions { width: 40px; text-align: right; }
    .del { background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 4px; border-radius: 4px; }
    .del:hover { color: var(--color-red); background: var(--color-red-bg); }
    .robot { font-family: var(--font-mono); font-size: 12px; color: #10b981; font-weight: 600; }
    .missing { color: var(--color-red); font-size: 12px; }
    .hint { display: block; font-size: 11px; color: var(--text-muted); margin-top: 4px; }
    .chip { display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 10px; background: rgba(99,102,241,.12); color: var(--color-indigo); margin: 0 4px 4px 0; }
    .muted { color: var(--text-muted); font-size: 12px; margin-top: 2px; }
    .mono { font-family: var(--font-mono); font-size: 12px; }
    .status { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; background: var(--color-gray-bg); color: var(--text-secondary); }
    .status[data-status=succeeded] { background: var(--color-green-bg); color: var(--color-green); }
    .status[data-status=failed] { background: var(--color-red-bg); color: var(--color-red); }
    .status[data-status=partial] { background: var(--color-amber-bg); color: var(--color-amber); }
    .status[data-status=running], .status[data-status=queued], .status[data-status=cancelling] { background: var(--color-blue-bg); color: var(--color-blue); }
    .empty-state { text-align: center; padding: 48px 24px; }
    .empty-state h3 { margin-bottom: 8px; }
    .empty-state p { color: var(--text-muted); font-size: 13px; margin-bottom: 16px; }
  `]
})
export class PipelineListComponent implements OnInit, OnDestroy {
  pipelines: any[] = [];
  showCreate = false;
  loaded = false;
  saving = false;
  error = '';
  form = { name: '', description: '', robot_code: '' };
  robots: any[] = [];
  private timer: any;

  constructor(private api: ApiService, private router: Router, private cdr: ChangeDetectorRef) {}

  ngOnInit() {
    this.load();
    this.api.getRobots().subscribe(r => { this.robots = r; this.cdr.detectChanges(); });
    this.timer = setInterval(() => this.load(), 5000);
  }

  triggerName(t: string) {
    return ({ 'trigger.manual': 'Manuel', 'trigger.schedule': 'Planifié', 'trigger.webhook': 'API' } as any)[t] || t;
  }

  ngOnDestroy() { clearInterval(this.timer); }

  load() {
    this.api.getPipelines().subscribe({
      next: p => { this.pipelines = p; this.loaded = true; this.cdr.detectChanges(); },
      error: () => { this.error = 'Impossible de charger les pipelines'; this.loaded = true; this.cdr.detectChanges(); },
    });
  }

  create() {
    this.saving = true;
    this.error = '';
    this.api.createPipeline(this.form).subscribe({
      next: p => this.router.navigate(['/pipelines', p.id]),
      error: e => { this.error = e.error?.detail || 'Erreur'; this.saving = false; this.cdr.detectChanges(); },
    });
  }

  remove(p: any) {
    if (!confirm(`Supprimer le workflow « ${p.name} » et son historique ? Cette action est définitive.`)) return;
    this.error = '';
    this.api.deletePipeline(p.id).subscribe({
      next: () => this.load(),
      error: e => { this.error = e.error?.detail || 'Suppression impossible'; this.cdr.detectChanges(); },
    });
  }

  open(id: string) { this.router.navigate(['/pipelines', id]); }
  statusLabel(s: string) { return RUN_STATUS_LABELS[s] || s; }
  triggerLabel(t: string) { return TRIGGER_LABELS[t] || t; }
}
