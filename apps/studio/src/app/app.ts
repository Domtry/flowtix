import { Component } from '@angular/core';
import { RouterOutlet, RouterModule } from '@angular/router';

@Component({
  imports: [RouterOutlet, RouterModule],
  selector: 'app-root',
  template: `
    <div class="layout">
      <aside class="sidebar">
        <a routerLink="/" class="logo">
          <span class="logo-icon">F</span>
          <span class="logo-text">FlowtTix</span>
        </a>
        <nav class="nav">
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
            Dashboard
          </a>
          <a routerLink="/processes" routerLinkActive="active" class="nav-item">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            Processes
          </a>
        </nav>
        <div class="sidebar-footer">
          <span class="version">v0.1.0</span>
        </div>
      </aside>
      <main class="content">
        <router-outlet />
      </main>
    </div>
  `,
  styles: [`
    .layout { display: flex; min-height: 100vh; }

    .sidebar {
      width: 220px;
      background: var(--bg-primary);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      z-index: 100;
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 20px 16px;
      text-decoration: none;
      color: var(--text-primary);
    }
    .logo-icon {
      width: 28px;
      height: 28px;
      background: var(--color-indigo);
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 14px;
      color: white;
    }
    .logo-text { font-weight: 700; font-size: 16px; }

    .nav {
      flex: 1;
      padding: 8px;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .nav-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 9px 12px;
      border-radius: var(--radius-md);
      color: var(--text-secondary);
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      transition: all 0.15s;
    }
    .nav-item:hover { background: var(--bg-hover); color: var(--text-primary); }
    .nav-item.active { background: var(--bg-active); color: white; }

    .sidebar-footer {
      padding: 16px;
      border-top: 1px solid var(--border-color);
    }
    .version { font-size: 11px; color: var(--text-muted); }

    .content {
      flex: 1;
      margin-left: 220px;
      min-height: 100vh;
    }
  `]
})
export class App {}
