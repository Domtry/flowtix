import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page">
      <h1>Settings</h1>
      <p class="subtitle">Configure your FlowtTix environment</p>

      @if (saved) {
        <div class="success-banner">Settings saved successfully.</div>
      }

      <div class="section card">
        <h2>Browser Agent</h2>
        <div class="form-field">
          <label>Browser Executable Path</label>
          <input [(ngModel)]="browserPath" placeholder="C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" class="mono" />
          <span class="hint">Absolute path to the browser used for recording and replay.</span>
        </div>
        <div class="form-field">
          <label>Agent URL</label>
          <input [(ngModel)]="agentUrl" placeholder="http://localhost:9090" class="mono" />
          <span class="hint">URL of the browser agent running on the host machine.</span>
        </div>
      </div>

      <div class="section card">
        <h2>Application</h2>
        <div class="form-field">
          <label>Default Replay Mode</label>
          <select [(ngModel)]="replayMode">
            <option value="headed">Headed (visible browser)</option>
            <option value="headless">Headless (background)</option>
          </select>
        </div>
        <div class="form-field">
          <label>Replay Slow-Mo (ms)</label>
          <input type="number" [(ngModel)]="slowMo" min="0" max="5000" />
          <span class="hint">Delay between replay actions for debugging (0 = no delay).</span>
        </div>
      </div>

      <div class="actions">
        <button class="btn-primary" (click)="save()">Save Settings</button>
      </div>

      <div class="section card smtp">
        <h2>Serveur e-mail (blocs « Envoyer un e-mail »)</h2>
        @if (smtpMsg) { <div class="msg" [class.ko]="smtpError">{{ smtpMsg }}</div> }
        <div class="grid">
          <div class="form-field">
            <label>Serveur SMTP</label>
            <input [(ngModel)]="smtp.host" placeholder="smtp.office365.com" class="mono" />
          </div>
          <div class="form-field">
            <label>Port</label>
            <input type="number" [(ngModel)]="smtp.port" />
          </div>
          <div class="form-field">
            <label>Sécurité</label>
            <select [(ngModel)]="smtp.security">
              <option value="starttls">STARTTLS (port 587)</option>
              <option value="ssl">SSL/TLS (port 465)</option>
              <option value="none">Aucune</option>
            </select>
          </div>
          <div class="form-field">
            <label>Expéditeur</label>
            <input [(ngModel)]="smtp.sender" placeholder="robot@sanlam.ci" />
          </div>
          <div class="form-field">
            <label>Identifiant</label>
            <input [(ngModel)]="smtp.username" autocomplete="off" />
          </div>
          <div class="form-field">
            <label>Mot de passe</label>
            <input type="password" [(ngModel)]="smtpPassword" autocomplete="new-password"
                   [placeholder]="smtpHasPassword ? '•••••••• (inchangé)' : ''" />
            <span class="hint">Stocké chiffré (AES-256-GCM), jamais réaffiché.</span>
          </div>
        </div>
        <div class="row">
          <button class="btn-primary" (click)="saveSmtp()" [disabled]="!smtp.host || !smtp.sender">Enregistrer le serveur</button>
          <input [(ngModel)]="testTo" placeholder="adresse de test" class="test-to" />
          <button class="btn-secondary" (click)="testSmtp()" [disabled]="!testTo || !smtpConfigured">Envoyer un test</button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .page { padding: 32px; max-width: 800px; }
    .subtitle { color: var(--text-muted); font-size: 13px; margin-top: 4px; margin-bottom: 24px; }
    .success-banner { padding: 10px 14px; background: var(--color-green-bg); color: var(--color-green); border-radius: var(--radius-md); margin-bottom: 16px; font-size: 13px; }
    .section { margin-bottom: 20px; }
    .section h2 { margin-bottom: 16px; }
    .form-field { margin-bottom: 16px; }
    .form-field label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); margin-bottom: 4px; font-weight: 600; }
    .form-field input, .form-field select { width: 100%; }
    .form-field input[type="number"] { width: 120px; }
    .hint { display: block; font-size: 11px; color: var(--text-muted); margin-top: 4px; }
    .mono { font-family: var(--font-mono); font-size: 13px; }
    .actions { margin-top: 8px; margin-bottom: 24px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
    .grid .form-field input[type="number"] { width: 100%; }
    .row { display: flex; gap: 10px; align-items: center; }
    .test-to { width: 220px; }
    .msg { padding: 8px 12px; border-radius: var(--radius-md); margin-bottom: 12px; font-size: 13px; background: var(--color-green-bg); color: var(--color-green); }
    .msg.ko { background: var(--color-red-bg); color: var(--color-red); }
  `]
})
export class SettingsComponent implements OnInit {
  browserPath = String.raw`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`;
  agentUrl = 'http://localhost:9090';
  replayMode = 'headed';
  slowMo = 100;
  saved = false;

  smtp: any = { host: '', port: 587, security: 'starttls', sender: '', username: '' };
  smtpPassword = '';
  smtpHasPassword = false;
  smtpConfigured = false;
  smtpMsg = '';
  smtpError = false;
  testTo = '';

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  private setSmtp(s: any) {
    if (s?.host) {
      this.smtp = { host: s.host, port: s.port, security: s.security, sender: s.sender, username: s.username };
      this.smtpHasPassword = s.has_password;
      this.smtpConfigured = true;
    }
  }

  saveSmtp() {
    // an empty field keeps the stored password
    const body = { ...this.smtp, password: this.smtpPassword ? this.smtpPassword : null };
    this.api.saveSmtp(body).subscribe({
      next: s => { this.setSmtp(s); this.smtpPassword = ''; this.smtpError = false; this.smtpMsg = 'Serveur e-mail enregistré'; this.cdr.detectChanges(); },
      error: e => { this.smtpError = true; this.smtpMsg = e.error?.detail?.[0]?.msg || e.error?.detail || 'Erreur'; this.cdr.detectChanges(); },
    });
  }

  testSmtp() {
    this.smtpMsg = 'Envoi en cours…';
    this.smtpError = false;
    this.api.testSmtp(this.testTo).subscribe({
      next: () => { this.smtpMsg = `E-mail de test envoyé à ${this.testTo}`; this.cdr.detectChanges(); },
      error: e => { this.smtpError = true; this.smtpMsg = e.error?.detail || 'Échec de l\'envoi'; this.cdr.detectChanges(); },
    });
  }

  ngOnInit() {
    this.api.getSmtp().subscribe(s => { this.setSmtp(s); this.cdr.detectChanges(); });
    this.api.getSettings().subscribe({
      next: settings => {
        for (const s of settings) {
          if (s.key === 'browser_path') this.browserPath = s.value;
          if (s.key === 'agent_url') this.agentUrl = s.value;
          if (s.key === 'replay_mode') this.replayMode = s.value;
          if (s.key === 'slow_mo') this.slowMo = parseInt(s.value, 10) || 100;
        }
        this.cdr.detectChanges();
      }
    });
  }

  save() {
    this.saved = false;
    const saves = [
      this.api.saveSetting('browser_path', this.browserPath),
      this.api.saveSetting('agent_url', this.agentUrl),
      this.api.saveSetting('replay_mode', this.replayMode),
      this.api.saveSetting('slow_mo', String(this.slowMo)),
    ];
    let done = 0;
    for (const obs of saves) {
      obs.subscribe({ next: () => { done++; if (done === saves.length) { this.saved = true; this.cdr.detectChanges(); } } });
    }
  }
}
