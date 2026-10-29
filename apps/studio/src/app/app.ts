import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterOutlet, RouterModule } from '@angular/router';

@Component({
  imports: [CommonModule, RouterOutlet, RouterModule],
  selector: 'app-root',
  template: `
    <div class="layout" [class.no-sidebar]="isLoginPage()">
      @if (!isLoginPage()) {
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
            <a routerLink="/pipelines" routerLinkActive="active" class="nav-item">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 6h6a4 4 0 0 1 4 4v6"/><polyline points="14 13 17 16 20 13"/></svg>
              Workflows
            </a>
            <a routerLink="/robots" routerLinkActive="active" class="nav-item">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/></svg>
              Robots
            </a>
            <a routerLink="/docs" routerLinkActive="active" class="nav-item">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/></svg>
              Documentation
            </a>
            <a routerLink="/settings" routerLinkActive="active" class="nav-item">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
              Settings
            </a>
          </nav>
          <div class="sidebar-footer">
            @if (currentUser) {
              <div class="user-info">
                <div class="user-avatar">{{ currentUser.name?.charAt(0)?.toUpperCase() }}</div>
                <div class="user-details">
                  <span class="user-name">{{ currentUser.name }}</span>
                  <span class="user-role">{{ currentUser.role }}</span>
                </div>
              </div>
              <button class="btn-ghost btn-sm logout-btn" (click)="logout()">Sign out</button>
            } @else {
              <a routerLink="/login" class="btn-ghost btn-sm login-btn">Sign in</a>
            }
            <span class="version">v0.1.0</span>
          </div>
        </aside>
      }
      <main class="content" [class.full-width]="isLoginPage()">
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
      padding: 12px 16px;
      border-top: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .user-info { display: flex; align-items: center; gap: 10px; }
    .user-avatar {
      width: 28px; height: 28px; border-radius: 50%;
      background: var(--color-indigo); color: white;
      display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-weight: 700;
    }
    .user-details { display: flex; flex-direction: column; }
    .user-name { font-size: 13px; font-weight: 500; }
    .user-role { font-size: 11px; color: var(--text-muted); text-transform: capitalize; }
    .logout-btn, .login-btn { width: 100%; text-align: center; font-size: 12px; }
    .version { font-size: 11px; color: var(--text-muted); text-align: center; }

    .content {
      flex: 1;
      margin-left: 220px;
      min-height: 100vh;
    }
    .content.full-width { margin-left: 0; }
  `]
})
export class App implements OnInit {
  currentUser: any = null;

  constructor(private router: Router) {}

  ngOnInit() {
    this.loadUser();
    this.router.events.subscribe(() => this.loadUser());
  }

  loadUser() {
    try {
      const raw = localStorage.getItem('flowtix_user');
      this.currentUser = raw ? JSON.parse(raw) : null;
    } catch { this.currentUser = null; }
  }

  isLoginPage(): boolean {
    return this.router.url === '/login';
  }

  logout() {
    localStorage.removeItem('flowtix_token');
    localStorage.removeItem('flowtix_user');
    this.currentUser = null;
    this.router.navigate(['/login']);
  }
}
