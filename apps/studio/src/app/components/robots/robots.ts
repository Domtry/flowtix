import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-robots',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="page">
      <div class="header-row">
        <div>
          <h1>Robots</h1>
          <p class="subtitle">Chaque robot cible une plateforme specifique a automatiser.</p>
        </div>
        <button class="btn-primary" (click)="showCreate = true" *ngIf="!showCreate">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Nouveau Robot
        </button>
      </div>

      @if (error) {
        <div class="error-banner">{{ error }}</div>
      }
      @if (success) {
        <div class="success-banner">{{ success }}</div>
      }

      <!-- Create form -->
      @if (showCreate) {
        <div class="card form-card">
          <h3>{{ editingRobot ? 'Modifier' : 'Nouveau' }} Robot</h3>
          <div class="form-grid">
            <div class="form-field">
              <label>Code</label>
              <input [(ngModel)]="form.code" placeholder="ROBO_MILLIARD" class="mono-input"
                     [disabled]="!!editingRobot" />
              <span class="hint">Identifiant unique, reutilisable (ex: ROBO_MILLIARD)</span>
            </div>
            <div class="form-field">
              <label>Nom</label>
              <input [(ngModel)]="form.name" placeholder="Robo Milliard" />
            </div>
          </div>
          <div class="form-field">
            <label>Description</label>
            <textarea [(ngModel)]="form.description" rows="2"
              placeholder="Robot pour automatiser la plateforme Milliard..."></textarea>
          </div>
          <div class="form-grid">
            <div class="form-field">
              <label>Type d'action</label>
              <select [(ngModel)]="form.action_type">
                <option value="web">Page Web</option>
                <option value="windows">Application Windows</option>
                <option value="java">Application Java</option>
                <option value="desktop">Bureau (Desktop)</option>
              </select>
            </div>
            <div class="form-field">
              <label>Moteur</label>
              <select [(ngModel)]="form.engine">
                <option value="auto">Auto</option>
                <option value="playwright">Playwright</option>
                <option value="selenium">Selenium</option>
                <option value="subprocess">Subprocess</option>
              </select>
            </div>
          </div>
          <div class="form-field">
            <label>Chemin executable</label>
            <input [(ngModel)]="form.executable_path" class="mono-input"
              placeholder="C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe" />
          </div>
          <div class="form-grid">
            <div class="form-field">
              <label>URL par defaut</label>
              <input [(ngModel)]="form.default_url" class="mono-input"
                placeholder="http://172.30.200.179:7778/" />
            </div>
            <div class="form-field">
              <label>Titre fenetre (filtre)</label>
              <input [(ngModel)]="form.window_title_pattern"
                placeholder="sanlam" />
              <span class="hint">Mot-cle dans le titre de la fenetre pour filtrer les evenements</span>
            </div>
          </div>
          <div class="form-actions">
            <button class="btn-primary" (click)="saveRobot()" [disabled]="!form.code || !form.name">
              {{ editingRobot ? 'Sauvegarder' : 'Creer' }}
            </button>
            <button class="btn-ghost" (click)="cancelCreate()">Annuler</button>
          </div>
        </div>
      }

      <!-- Robot list -->
      <div class="robot-grid">
        @for (robot of robots; track robot.code) {
          <div class="card robot-card" [class.active]="expandedRobot === robot.code"
               (click)="expandedRobot = expandedRobot === robot.code ? '' : robot.code">
            <div class="robot-header">
              <div class="robot-icon" [attr.data-type]="robot.action_type">
                @switch (robot.action_type) {
                  @case ('web') { 🌐 }
                  @case ('java') { ☕ }
                  @case ('windows') { 🪟 }
                  @default { 🖥️ }
                }
              </div>
              <div class="robot-info">
                <span class="robot-code">{{ robot.code }}</span>
                <span class="robot-name">{{ robot.name }}</span>
              </div>
              <div class="robot-badges">
                <span class="badge" [attr.data-engine]="robot.engine">{{ robot.engine }}</span>
                <span class="badge badge-type">{{ robot.action_type }}</span>
              </div>
            </div>
            @if (robot.description) {
              <p class="robot-desc">{{ robot.description }}</p>
            }
            @if (expandedRobot === robot.code) {
              <div class="robot-details" (click)="$event.stopPropagation()">
                @if (robot.executable_path) {
                  <div class="detail-row">
                    <span class="detail-label">Executable</span>
                    <span class="detail-value mono">{{ robot.executable_path }}</span>
                  </div>
                }
                @if (robot.default_url) {
                  <div class="detail-row">
                    <span class="detail-label">URL</span>
                    <span class="detail-value mono">{{ robot.default_url }}</span>
                  </div>
                }
                @if (robot.window_title_pattern) {
                  <div class="detail-row">
                    <span class="detail-label">Filtre fenetre</span>
                    <span class="detail-value">{{ robot.window_title_pattern }}</span>
                  </div>
                }
                <div class="robot-actions">
                  <button class="btn-ghost btn-sm" (click)="editRobot(robot)">Modifier</button>
                  <button class="btn-danger btn-sm" (click)="deleteRobot(robot.code)">Supprimer</button>
                </div>
              </div>
            }
          </div>
        }
      </div>

      @if (!robots.length && !showCreate) {
        <div class="card empty-state">
          <div class="empty-icon">🤖</div>
          <h3>Aucun robot configure</h3>
          <p>Creez votre premier robot pour commencer a automatiser une plateforme.</p>
          <button class="btn-primary" (click)="showCreate = true">Creer un robot</button>
        </div>
      }
    </div>
  `,
  styles: [`
    .page { padding: 32px; max-width: 1000px; }
    .header-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
    .subtitle { color: var(--text-muted); font-size: 13px; margin: 4px 0 0; }
    .error-banner { padding: 10px 14px; background: var(--color-red-bg); color: var(--color-red); border-radius: var(--radius-md); margin-bottom: 16px; font-size: 13px; }
    .success-banner { padding: 10px 14px; background: var(--color-green-bg); color: var(--color-green); border-radius: var(--radius-md); margin-bottom: 16px; font-size: 13px; }

    .form-card { margin-bottom: 24px; }
    .form-card h3 { margin-bottom: 16px; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .form-field { margin-bottom: 14px; }
    .form-field label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); margin-bottom: 4px; font-weight: 600; }
    .form-field input, .form-field select, .form-field textarea { width: 100%; }
    .form-field textarea { resize: vertical; }
    .hint { display: block; font-size: 11px; color: var(--text-muted); margin-top: 4px; }
    .mono-input { font-family: var(--font-mono); font-size: 13px; }
    .form-actions { display: flex; gap: 10px; margin-top: 8px; }

    .robot-grid { display: flex; flex-direction: column; gap: 12px; }
    .robot-card { cursor: pointer; transition: border-color 0.15s; }
    .robot-card:hover { border-color: var(--color-indigo); }
    .robot-card.active { border-color: var(--color-indigo); }
    .robot-header { display: flex; align-items: center; gap: 12px; }
    .robot-icon { font-size: 24px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; background: var(--bg-secondary); border-radius: var(--radius-md); }
    .robot-info { flex: 1; display: flex; flex-direction: column; }
    .robot-code { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; }
    .robot-name { font-weight: 600; font-size: 15px; }
    .robot-badges { display: flex; gap: 6px; }
    .badge { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; background: var(--bg-secondary); color: var(--text-muted); }
    .badge-type { background: var(--color-indigo-bg, rgba(99,102,241,0.1)); color: var(--color-indigo); }
    .robot-desc { font-size: 13px; color: var(--text-secondary); margin: 8px 0 0; }
    .robot-details { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-color); }
    .detail-row { display: flex; gap: 12px; margin-bottom: 6px; font-size: 13px; }
    .detail-label { min-width: 100px; color: var(--text-muted); font-weight: 500; }
    .detail-value { color: var(--text-primary); }
    .mono { font-family: var(--font-mono); font-size: 12px; }
    .robot-actions { display: flex; gap: 8px; margin-top: 12px; }

    .empty-state { text-align: center; padding: 48px 24px; }
    .empty-icon { font-size: 48px; margin-bottom: 12px; }
    .empty-state h3 { margin-bottom: 8px; }
    .empty-state p { color: var(--text-muted); font-size: 13px; margin-bottom: 16px; }
  `]
})
export class RobotsComponent implements OnInit {
  robots: any[] = [];
  showCreate = false;
  editingRobot: any = null;
  expandedRobot = '';
  error = '';
  success = '';

  form: any = {
    code: '', name: '', description: '',
    action_type: 'web', engine: 'subprocess',
    executable_path: '', default_url: '', window_title_pattern: '',
  };

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit() {
    this.loadRobots();
  }

  loadRobots() {
    this.api.getRobots().subscribe({
      next: robots => { this.robots = robots; this.cdr.detectChanges(); },
      error: () => { this.error = 'Impossible de charger les robots'; this.cdr.detectChanges(); }
    });
  }

  saveRobot() {
    this.error = '';
    if (this.editingRobot) {
      this.api.updateRobot(this.editingRobot.code, this.form).subscribe({
        next: () => {
          this.success = `Robot "${this.form.code}" mis a jour`;
          this.cancelCreate();
          this.loadRobots();
        },
        error: (e) => { this.error = e.error?.detail || 'Erreur'; this.cdr.detectChanges(); }
      });
    } else {
      this.api.createRobot(this.form).subscribe({
        next: () => {
          this.success = `Robot "${this.form.code}" cree`;
          this.cancelCreate();
          this.loadRobots();
        },
        error: (e) => { this.error = e.error?.detail || 'Erreur'; this.cdr.detectChanges(); }
      });
    }
  }

  editRobot(robot: any) {
    this.editingRobot = robot;
    this.form = { ...robot };
    this.showCreate = true;
    this.cdr.detectChanges();
  }

  deleteRobot(code: string) {
    this.api.deleteRobot(code).subscribe({
      next: () => {
        this.success = `Robot "${code}" supprime`;
        this.loadRobots();
      },
      error: (e) => { this.error = e.error?.detail || 'Erreur'; this.cdr.detectChanges(); }
    });
  }

  cancelCreate() {
    this.showCreate = false;
    this.editingRobot = null;
    this.form = {
      code: '', name: '', description: '',
      action_type: 'web', engine: 'subprocess',
      executable_path: '', default_url: '', window_title_pattern: '',
    };
    this.cdr.detectChanges();
  }
}
