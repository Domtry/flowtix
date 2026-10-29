import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-recording',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="page">
      <div class="breadcrumb">
        <a routerLink="/processes">Processes</a>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        <a [routerLink]="['/processes', processId]">Process</a>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
        <span>Record</span>
      </div>

      <div class="header-row">
        <div>
          <h1>Record Session</h1>
          <p class="subtitle">Configure the agent, then start recording your actions.</p>
        </div>
      </div>

      @if (error) {
        <div class="error-banner">{{ error }}</div>
      }
      @if (successMsg) {
        <div class="success-banner">{{ successMsg }}</div>
      }

      <!-- Not Recording: configuration panel -->
      @if (state === 'idle') {
        <div class="card config-card">
          <h3>Agent Configuration</h3>

          @if (robots.length) {
            <div class="form-field module-selector">
              <label>Robot</label>
              <div class="module-chips">
                <button
                  class="chip"
                  [class.active]="!selectedRobot"
                  (click)="selectRobot(null)"
                >Custom</button>
                @for (r of robots; track r.code) {
                  <button
                    class="chip"
                    [class.active]="selectedRobot?.code === r.code"
                    (click)="selectRobot(r)"
                  >
                    <span class="chip-code">{{ r.code }}</span>
                    <span class="chip-name">{{ r.name }}</span>
                  </button>
                }
              </div>
            </div>
          }

          <div class="config-grid">
            <div class="form-field">
              <label>Action Type</label>
              <select [(ngModel)]="actionType">
                <option value="web">Page Web</option>
                <option value="windows">Application Windows</option>
                <option value="java">Application Java</option>
                <option value="desktop">Bureau (Desktop)</option>
              </select>
              <span class="hint">
                @switch (actionType) {
                  @case ('web') { Ouvre un navigateur et enregistre les interactions web. }
                  @case ('windows') { Pilote une application Windows native via UI Automation. }
                  @case ('java') { Pilote une application Java via Java Access Bridge. }
                  @case ('desktop') { Capture les actions souris/clavier sur le bureau. }
                }
              </span>
            </div>

            <div class="form-field">
              <label>Engine</label>
              <select [(ngModel)]="engine">
                <option value="auto">Auto (selon le navigateur)</option>
                <option value="playwright">Playwright (Chromium: Edge, Chrome)</option>
                <option value="selenium">Selenium (Firefox, Chrome, Edge)</option>
                <option value="subprocess">Subprocess (lancement direct)</option>
              </select>
              <span class="hint">
                @switch (engine) {
                  @case ('auto') { Playwright pour Edge/Chrome, Selenium pour Firefox et autres. }
                  @case ('playwright') { Rapide, CDP natif. Uniquement navigateurs Chromium. }
                  @case ('selenium') { Compatible tous navigateurs recents via WebDriver. }
                  @case ('subprocess') { Lance l'application directement. Compatible toutes versions. }
                }
              </span>
            </div>
          </div>

          @if (actionType === 'web') {
            <label class="session-box" [class.on]="keepSession">
              <input type="checkbox" [(ngModel)]="keepSession" />
              <span>
                <strong>Continuer dans la session en cours</strong> — ne pas lancer l'application
                <span class="hint">L'enregistrement démarre dans la fenêtre déjà ouverte (ex. ORASS connecté, sur l'écran de départ).
                  Le processus ne contiendra ni ouverture ni connexion : idéal pour une variante qui s'enchaîne dans un workflow.
                  Utilise le mode Subprocess.</span>
              </span>
            </label>

            <div class="form-field">
              <label>Browser Path</label>
              <input
                [(ngModel)]="browserPath"
                placeholder="C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe"
                class="mono-input"
              />
              <span class="hint">Chemin absolu vers l'executable du navigateur a utiliser.</span>
            </div>

            <div class="form-field">
              <label>Target URL</label>
              <div class="url-row">
                <input
                  [(ngModel)]="targetUrl"
                  placeholder="https://example.com"
                  class="url-input"
                  (keydown.enter)="startRecording()"
                />
                <button class="btn-primary btn-lg" (click)="startRecording()" [disabled]="!targetUrl.trim() && !keepSession">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="6" fill="var(--color-red)"/></svg>
                  Start Recording
                </button>
              </div>
            </div>
          }

          @if (actionType === 'windows' || actionType === 'java') {
            <div class="form-field">
              <label>Application Path</label>
              <input
                [(ngModel)]="appPath"
                placeholder="C:\\Program Files\\MyApp\\app.exe"
                class="mono-input"
              />
              <span class="hint">Chemin vers l'application a lancer et piloter.</span>
            </div>

            <div class="form-field">
              <label>Window Title (optional)</label>
              <input
                [(ngModel)]="windowTitle"
                placeholder="My Application - Main Window"
              />
              <span class="hint">Titre de la fenetre a cibler si l'application est deja ouverte.</span>
            </div>

            <button class="btn-primary btn-lg" (click)="startRecording()" [disabled]="!appPath.trim()">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="6" fill="var(--color-red)"/></svg>
              Start Recording
            </button>
            <p class="hint agent-hint">Necessite l'agent Windows (agents/windows) en cours d'execution.</p>
          }

          @if (actionType === 'desktop') {
            <button class="btn-primary btn-lg" (click)="startRecording()">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="6" fill="var(--color-red)"/></svg>
              Start Recording
            </button>
            <p class="hint agent-hint">Capture les actions souris et clavier sur tout le bureau.</p>
          }
        </div>
      }

      <!-- Recording in progress -->
      @if (state === 'recording') {
        <div class="card recording-card">
          <div class="recording-header">
            <div class="rec-indicator">
              <span class="rec-dot"></span>
              <span>Recording...</span>
            </div>
            <div class="rec-meta">
              <span class="badge-engine">{{ activeEngine }}</span>
              <span class="mono">{{ events.length }} events</span>
            </div>
            <button class="btn-danger btn-lg" (click)="stopRecording()">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="6" width="12" height="12" fill="currentColor" rx="1"/></svg>
              Stop Recording
            </button>
          </div>
          <div class="target-url mono">{{ targetUrl }}</div>
        </div>

        <!-- Live event feed -->
        @if (events.length) {
          <div class="card events-card">
            <h3>Captured Events</h3>
            <div class="event-list">
              @for (ev of events; track $index; let i = $index) {
                <div class="event-row" [class.recent]="i >= events.length - 3">
                  <span class="ev-num">{{ i + 1 }}</span>
                  <span class="ev-type" [attr.data-type]="ev.event_type">{{ ev.event_type }}</span>
                  <span class="ev-target">{{ ev.target?.selector || ev.target?.tag || '' }}</span>
                  @if (ev.value) {
                    <span class="ev-value mono">{{ ev.value }}</span>
                  }
                </div>
              }
            </div>
          </div>
        }
      }

      <!-- Stopping -->
      @if (state === 'stopping') {
        <div class="card">
          <div class="stopping-indicator">
            <span class="spinner"></span>
            <span>Stopping recording and saving version...</span>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .page { padding: 32px; max-width: 900px; }
    .breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-muted); margin-bottom: 20px; }
    .breadcrumb a { color: var(--text-accent); }
    .breadcrumb span:last-child { color: var(--text-primary); }
    .subtitle { color: var(--text-muted); font-size: 13px; margin: 4px 0 0; }
    .header-row { margin-bottom: 20px; }

    .error-banner { padding: 10px 14px; background: var(--color-red-bg); color: var(--color-red); border-radius: var(--radius-md); margin-bottom: 16px; font-size: 13px; }
    .success-banner { padding: 10px 14px; background: var(--color-green-bg); color: var(--color-green); border-radius: var(--radius-md); margin-bottom: 16px; font-size: 13px; }

    .config-card h3 { margin-bottom: 16px; }
    .config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
    .form-field { margin-bottom: 14px; }
    .form-field label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); margin-bottom: 4px; font-weight: 600; }
    .form-field select, .form-field input { width: 100%; }
    .hint { display: block; font-size: 11px; color: var(--text-muted); margin-top: 4px; }
    .agent-hint { margin-top: 10px; }
    .mono-input { font-family: var(--font-mono); font-size: 13px; }
    .url-row { display: flex; gap: 10px; }
    .url-input { flex: 1; font-family: var(--font-mono); font-size: 14px; padding: 10px 14px; }
    .btn-lg { padding: 10px 20px; font-size: 14px; display: flex; align-items: center; gap: 8px; }

    .recording-card { border-color: var(--color-red); }
    .recording-header { display: flex; align-items: center; gap: 16px; }
    .rec-indicator { display: flex; align-items: center; gap: 8px; font-weight: 600; color: var(--color-red); }
    .rec-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--color-red); animation: blink 1s infinite; }
    @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.2; } }
    .rec-meta { flex: 1; text-align: right; display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
    .session-box { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; margin-bottom: 16px; cursor: pointer;
      border: 1px solid var(--border-color); border-radius: var(--radius-md); font-size: 13px; text-transform: none; letter-spacing: 0; }
    .session-box.on { border-color: rgba(16,185,129,.5); background: rgba(16,185,129,.08); }
    .session-box input { width: auto; margin-top: 3px; }
    .badge-engine {
      font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em;
      padding: 2px 8px; border-radius: 10px;
      background: var(--color-indigo-bg, rgba(99,102,241,0.1)); color: var(--color-indigo);
    }
    .target-url { margin-top: 8px; color: var(--text-muted); font-size: 12px; }
    .mono { font-family: var(--font-mono); font-size: 12px; }

    .events-card { margin-top: 16px; }
    .events-card h3 { margin-bottom: 12px; }
    .event-list { max-height: 400px; overflow-y: auto; display: flex; flex-direction: column; gap: 3px; }
    .event-row {
      display: flex; align-items: center; gap: 10px;
      padding: 6px 10px;
      background: var(--bg-primary);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      font-size: 12px;
    }
    .event-row.recent { border-color: var(--color-blue); background: var(--color-blue-bg); }
    .ev-num { min-width: 24px; text-align: center; color: var(--text-muted); font-weight: 700; font-size: 10px; }
    .ev-type {
      display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px;
      text-transform: uppercase; letter-spacing: .05em; font-weight: 600;
      background: rgba(99,102,241,0.1); color: var(--color-indigo);
    }
    .ev-type[data-type="click"] { background: rgba(16,185,129,0.1); color: var(--color-green); }
    .ev-type[data-type="input"] { background: rgba(245,158,11,0.1); color: #f59e0b; }
    .ev-type[data-type="navigate"] { background: rgba(59,130,246,0.1); color: var(--color-blue); }
    .ev-type[data-type="keydown"] { background: rgba(168,85,247,0.1); color: #a855f7; }
    .ev-target { flex: 1; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ev-value { color: var(--color-green); max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .module-selector { margin-bottom: 16px; }
    .module-chips { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip {
      display: flex; align-items: center; gap: 6px;
      padding: 6px 14px; border-radius: 20px; font-size: 12px;
      background: var(--bg-primary); border: 1px solid var(--border-color);
      color: var(--text-secondary); cursor: pointer; transition: all 0.15s;
    }
    .chip:hover { border-color: var(--color-indigo); color: var(--text-primary); }
    .chip.active { background: var(--color-indigo-bg, rgba(99,102,241,0.1)); border-color: var(--color-indigo); color: var(--color-indigo); font-weight: 600; }
    .chip-code { font-family: var(--font-mono); font-size: 10px; text-transform: uppercase; letter-spacing: .05em; opacity: 0.7; }
    .chip-name { }

    .stopping-indicator { display: flex; align-items: center; gap: 12px; padding: 24px; }
    .spinner { width: 20px; height: 20px; border: 2px solid var(--border-color); border-top-color: var(--color-indigo); border-radius: 50%; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
  `]
})
export class RecordingComponent implements OnInit, OnDestroy {
  processId = '';
  targetUrl = 'https://';
  browserPath = String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`;
  actionType = 'web';
  engine = 'auto';
  appPath = '';
  windowTitle = '';
  keepSession = false;
  activeEngine = '';
  state: 'idle' | 'recording' | 'stopping' = 'idle';
  sessionId = '';
  events: any[] = [];
  error = '';
  successMsg = '';
  robots: any[] = [];
  selectedRobot: any = null;
  private pollTimer: any = null;

  constructor(
    private api: ApiService,
    private route: ActivatedRoute,
    private router: Router,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit() {
    this.processId = this.route.snapshot.paramMap.get('id') || '';
    this.api.getSettings().subscribe({
      next: settings => {
        for (const s of settings) {
          if (s.key === 'browser_path' && s.value) this.browserPath = s.value;
          if (s.key === 'default_action_type' && s.value) this.actionType = s.value;
          if (s.key === 'default_engine' && s.value) this.engine = s.value;
        }
        this.cdr.detectChanges();
      }
    });
    this.api.getRobots().subscribe({
      next: robots => {
        this.robots = robots;
        // Auto-select robot if process has one
        if (this.processId) {
          this.api.getProcess(this.processId).subscribe({
            next: (proc: any) => {
              if (proc.robot_code) {
                const robot = this.robots.find((r: any) => r.code === proc.robot_code);
                if (robot) this.selectRobot(robot);
              }
              this.cdr.detectChanges();
            }
          });
        }
        this.cdr.detectChanges();
      }
    });
  }

  selectRobot(r: any) {
    this.selectedRobot = r;
    if (r) {
      this.actionType = r.action_type || 'web';
      this.engine = r.engine || 'auto';
      this.browserPath = r.executable_path || this.browserPath;
      this.targetUrl = r.default_url || this.targetUrl;
      this.appPath = r.executable_path || '';
      this.windowTitle = r.window_title_pattern || '';
    }
    this.cdr.detectChanges();
  }

  ngOnDestroy() {
    if (this.pollTimer) clearInterval(this.pollTimer);
  }

  startRecording() {
    this.error = '';
    this.events = [];

    if (this.actionType === 'web') {
      if (!this.targetUrl.trim() && !this.keepSession) return;
      this.api.startRecording(this.processId, this.targetUrl.trim(), {
        browserPath: this.browserPath.trim(),
        actionType: this.actionType,
        engine: this.keepSession ? 'subprocess' : this.engine,
        windowTitlePattern: this.windowTitle || (this.selectedRobot?.window_title_pattern) || '',
        keepSession: this.keepSession,
      }).subscribe({
        next: (resp: any) => {
          this.sessionId = resp.id;
          this.activeEngine = resp.engine || this.engine;
          this.state = 'recording';
          this.startPollingEvents();
          this.cdr.detectChanges();
        },
        error: (err) => {
          this.error = err.error?.detail || 'Failed to start recording. Is the browser agent running?';
          this.cdr.detectChanges();
        }
      });
    } else {
      this.error = `Action type "${this.actionType}" requires the corresponding agent (not yet connected).`;
      this.cdr.detectChanges();
    }
  }

  stopRecording() {
    if (!this.sessionId) return;
    this.state = 'stopping';
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
    this.cdr.detectChanges();

    this.api.stopRecording(this.sessionId).subscribe({
      next: (resp: any) => {
        this.router.navigate(['/processes', this.processId]);
      },
      error: (err) => {
        this.state = 'recording';
        this.error = err.error?.detail || 'Failed to stop recording';
        this.cdr.detectChanges();
      }
    });
  }

  private startPollingEvents() {
    this.pollTimer = setInterval(() => {
      if (this.state !== 'recording' || !this.sessionId) return;
      this.api.getRecordingEvents(this.sessionId).subscribe({
        next: (events: any[]) => {
          this.events = events;
          this.cdr.detectChanges();
        },
        error: () => {}
      });
    }, 1000);
  }
}
