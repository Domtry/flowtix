import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-recording',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="recording-page">
      <header>
        <h1>Record Process</h1>
      </header>

      <div class="recording-controls" *ngIf="!sessionId">
        <label>Target URL:</label>
        <input [(ngModel)]="targetUrl" placeholder="https://example.com" class="url-input" />
        <button class="btn-record" (click)="startRecording()" [disabled]="!targetUrl">
          Start Recording
        </button>
      </div>

      <div class="recording-active" *ngIf="sessionId && isRecording">
        <div class="recording-indicator">
          <span class="dot"></span> Recording in progress...
        </div>
        <p>Perform your actions in the browser window. Events are captured automatically.</p>
        <div class="event-count">Events captured: {{ eventCount }}</div>
        <button class="btn-stop" (click)="stopRecording()">Stop Recording</button>
      </div>

      <div class="recording-done" *ngIf="sessionId && !isRecording">
        <h2>Recording Complete</h2>
        <p>{{ eventCount }} events captured.</p>
        <button class="btn-primary" (click)="saveAsVersion()">Save as Version</button>
        <button class="btn-secondary" (click)="viewEvents()">View Events</button>
      </div>

      <div class="events-preview" *ngIf="showEvents && events.length">
        <h3>Captured Events</h3>
        <div class="event-list">
          <div *ngFor="let evt of events; let i = index" class="event-item">
            <span class="event-num">{{ i + 1 }}</span>
            <span class="event-type">{{ evt.event_type }}</span>
            <span class="event-detail">{{ evt.target?.selector || evt.url || '' }}</span>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .recording-page { padding: 24px; max-width: 800px; margin: 0 auto; }
    .recording-controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 24px; }
    .url-input { flex: 1; min-width: 300px; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; }
    .btn-record { background: #dc2626; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; }
    .btn-stop { background: #dc2626; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
    .btn-primary { background: #4f46e5; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; margin-right: 8px; }
    .btn-secondary { background: #e2e8f0; color: #1e293b; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
    .recording-indicator { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 600; color: #dc2626; margin-bottom: 12px; }
    .dot { width: 12px; height: 12px; background: #dc2626; border-radius: 50%; animation: pulse 1s infinite; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .4; } }
    .event-count { font-size: 24px; font-weight: 700; margin: 16px 0; }
    .events-preview { margin-top: 24px; }
    .event-list { max-height: 400px; overflow-y: auto; }
    .event-item { display: flex; gap: 12px; padding: 6px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
    .event-num { color: #94a3b8; min-width: 30px; }
    .event-type { font-weight: 600; min-width: 100px; color: #4f46e5; }
    .event-detail { color: #64748b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
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
  private pollInterval: any;

  constructor(private api: ApiService, private route: ActivatedRoute, private router: Router) {}

  ngOnInit() {
    this.processId = this.route.snapshot.paramMap.get('id') || '';
  }

  ngOnDestroy() {
    if (this.pollInterval) clearInterval(this.pollInterval);
  }

  startRecording() {
    this.api.startRecording(this.processId, this.targetUrl).subscribe(session => {
      this.sessionId = session.id;
      this.isRecording = true;
      this.pollInterval = setInterval(() => this.pollEvents(), 2000);
    });
  }

  pollEvents() {
    if (!this.sessionId) return;
    this.api.getRecordingEvents(this.sessionId).subscribe(events => {
      this.eventCount = events.length;
    });
  }

  stopRecording() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.api.stopRecording(this.sessionId).subscribe(result => {
      this.isRecording = false;
      this.eventCount = result.event_count;
    });
  }

  viewEvents() {
    this.api.getRecordingEvents(this.sessionId).subscribe(events => {
      this.events = events;
      this.showEvents = true;
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
            type: this._mapEventType(evt.event_type),
            label: evt.event_type + (evt.target?.selector ? ` on ${evt.target.selector}` : ''),
            target: evt.target ? { strategy: 'dom', selector: evt.target.selector || '' } : undefined,
            value: evt.value || undefined,
            params: evt.metadata || undefined,
          })),
        },
      };
      this.api.createVersion(this.processId, definition).subscribe(() => {
        this.router.navigate(['/processes', this.processId, 'edit']);
      });
    });
  }

  private _mapEventType(eventType: string): string {
    const map: Record<string, string> = {
      click: 'ui.click', dblclick: 'ui.dblclick', input: 'ui.fill', change: 'ui.select',
      keydown: 'keyboard.press', scroll: 'ui.scroll', navigate: 'browser.navigate',
      page_load: 'browser.wait',
    };
    return map[eventType] || eventType;
  }
}
