import { Component, OnInit, OnDestroy } from '@angular/core';
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
        <span>Recording</span>
      </div>

      <h1>Record Session</h1>
      <p class="subtitle">Capture browser actions to automatically generate process steps.</p>

      <!-- Setup Phase -->
      <div class="setup card" *ngIf="!sessionId">
        <div class="form-group">
          <label>Target URL</label>
          <div class="url-row">
            <input [(ngModel)]="targetUrl" placeholder="https://example.com" class="url-input" (keydown.enter)="startRecording()" />
            <button class="btn-record" (click)="startRecording()" [disabled]="!targetUrl.trim()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="6" fill="currentColor"/></svg>
              Start Recording
            </button>
          </div>
        </div>
        @if (error) {
          <p class="error-msg">{{ error }}</p>
        }
      </div>

      <!-- Recording Active -->
      <div class="active-recording card" *ngIf="sessionId && isRecording">
        <div class="recording-header">
          <div class="rec-indicator">
            <span class="rec-dot"></span>
            <span class="badge recording">Recording</span>
          </div>
          <button class="btn-danger" (click)="stopRecording()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor"/></svg>
            Stop
          </button>
        </div>
        <p class="text-muted">Perform your actions in the browser window. Events are captured automatically.</p>
        <div class="event-counter">
          <span class="counter-value">{{ eventCount }}</span>
          <span class="counter-label">events captured</span>
        </div>
        <div class="target-url mono">{{ targetUrl }}</div>
      </div>

      <!-- Recording Done -->
      <div class="done card" *ngIf="sessionId && !isRecording">
        <div class="done-header">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--color-green)" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="16 8 10.5 14 8 11.5"/></svg>
          <div>
            <h2>Recording Complete</h2>
            <p class="text-muted">{{ eventCount }} events captured from {{ targetUrl }}</p>
          </div>
        </div>
        <div class="done-actions">
          <button class="btn-primary" (click)="saveAsVersion()">Save as Version</button>
          <button class="btn-secondary" (click)="viewEvents()">{{ showEvents ? 'Hide' : 'View' }} Events</button>
        </div>
      </div>

      <!-- Event List -->
      <div class="events-section card" *ngIf="showEvents && events.length">
        <h3>Captured Events ({{ events.length }})</h3>
        <div class="event-table">
          <table>
            <thead>
              <tr><th>#</th><th>Type</th><th>Target</th><th>Value</th></tr>
            </thead>
            <tbody>
              <tr *ngFor="let evt of events; let i = index">
                <td class="mono text-muted">{{ i + 1 }}</td>
                <td><span class="badge created">{{ evt.event_type }}</span></td>
                <td class="mono text-muted ellipsis">{{ evt.target?.selector || evt.url || '—' }}</td>
                <td class="mono text-muted">{{ evt.value || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .page { padding: 32px; max-width: 900px; }
    .breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-muted); margin-bottom: 20px; }
    .breadcrumb a { color: var(--text-accent); }
    .breadcrumb span:last-child { color: var(--text-primary); }
    .subtitle { color: var(--text-muted); font-size: 13px; margin: 4px 0 24px; }

    .form-group label { display: block; font-size: 12px; text-transform: uppercase; color: var(--text-muted); letter-spacing: .05em; margin-bottom: 6px; }
    .url-row { display: flex; gap: 8px; }
    .url-input { flex: 1; }
    .btn-record {
      display: flex; align-items: center; gap: 6px;
      background: #dc2626; color: white; padding: 8px 16px;
    }
    .btn-record:hover { background: #ef4444; }
    .btn-record:disabled { opacity: 0.4; cursor: not-allowed; }
    .error-msg { color: var(--color-red); font-size: 13px; margin-top: 8px; }

    .active-recording { }
    .recording-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .rec-indicator { display: flex; align-items: center; gap: 8px; }
    .rec-dot { width: 10px; height: 10px; border-radius: 50%; background: #dc2626; animation: rec-pulse 1s infinite; }
    @keyframes rec-pulse { 0%,100% { opacity: 1; box-shadow: 0 0 0 0 rgba(220,38,38,.4); } 50% { opacity: 0.6; box-shadow: 0 0 0 6px rgba(220,38,38,0); } }
    .event-counter { display: flex; align-items: baseline; gap: 8px; margin: 20px 0; }
    .counter-value { font-size: 48px; font-weight: 800; color: var(--text-primary); }
    .counter-label { font-size: 14px; color: var(--text-muted); }
    .target-url { padding: 8px 12px; background: var(--bg-primary); border-radius: var(--radius-md); color: var(--text-muted); }
    .text-muted { color: var(--text-muted); }

    .done-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
    .done-header h2 { margin-bottom: 2px; }
    .done-actions { display: flex; gap: 8px; }

    .events-section { margin-top: 16px; }
    .events-section h3 { margin-bottom: 12px; }
    .event-table { max-height: 400px; overflow-y: auto; }
    .mono { font-family: var(--font-mono); font-size: 12px; }
    .ellipsis { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  `]
})
export class RecordingComponent implements OnInit, OnDestroy {
  processId = '';
  targetUrl = '';
  sessionId = '';
  isRecording = false;
  eventCount = 0;
  events: any[] = [];
  showEvents = false;
  error = '';
  private pollInterval: any;

  constructor(private api: ApiService, private route: ActivatedRoute, private router: Router) {}

  ngOnInit() {
    this.processId = this.route.snapshot.paramMap.get('id') || '';
  }

  ngOnDestroy() {
    if (this.pollInterval) clearInterval(this.pollInterval);
  }

  startRecording() {
    if (!this.targetUrl.trim()) return;
    this.error = '';
    this.api.startRecording(this.processId, this.targetUrl).subscribe({
      next: session => {
        this.sessionId = session.id;
        this.isRecording = true;
        this.pollInterval = setInterval(() => this.pollEvents(), 2000);
      },
      error: err => {
        this.error = err.error?.detail || 'Failed to start recording';
      }
    });
  }

  pollEvents() {
    if (!this.sessionId) return;
    this.api.getRecordingEvents(this.sessionId).subscribe({
      next: events => this.eventCount = events.length,
      error: () => {}
    });
  }

  stopRecording() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.api.stopRecording(this.sessionId).subscribe({
      next: result => {
        this.isRecording = false;
        this.eventCount = result.event_count;
      },
      error: () => this.isRecording = false
    });
  }

  viewEvents() {
    if (this.showEvents) {
      this.showEvents = false;
      return;
    }
    this.api.getRecordingEvents(this.sessionId).subscribe({
      next: events => {
        this.events = events;
        this.showEvents = true;
      },
      error: () => {}
    });
  }

  saveAsVersion() {
    this.api.getRecordingEvents(this.sessionId).subscribe(events => {
      const definition = {
        schema_version: '1.0',
        process: {
          id: this.processId,
          name: 'Recorded session',
          steps: events.map((evt: any, i: number) => ({
            id: `step-${i + 1}`,
            type: this.mapEventType(evt.event_type),
            label: evt.event_type + (evt.target?.selector ? ` on ${evt.target.selector}` : ''),
            target: evt.target ? { strategy: 'dom', selector: evt.target.selector || '' } : undefined,
            value: evt.value || undefined,
            params: evt.metadata || undefined,
          })),
        },
      };
      this.api.createVersion(this.processId, definition).subscribe({
        next: () => this.router.navigate(['/processes', this.processId, 'edit']),
        error: () => this.error = 'Failed to save version'
      });
    });
  }

  private mapEventType(eventType: string): string {
    const map: Record<string, string> = {
      click: 'ui.click', dblclick: 'ui.dblclick', input: 'ui.fill', change: 'ui.select',
      keydown: 'keyboard.press', scroll: 'ui.scroll', navigate: 'browser.navigate',
      page_load: 'browser.wait',
    };
    return map[eventType] || eventType;
  }
}
