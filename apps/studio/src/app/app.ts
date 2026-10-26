import { Component } from '@angular/core';
import { RouterOutlet, RouterModule } from '@angular/router';

@Component({
  imports: [RouterOutlet, RouterModule],
  selector: 'app-root',
  template: `
    <nav class="top-nav">
      <a routerLink="/" class="logo">FlowtTix</a>
      <div class="nav-links">
        <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}">Dashboard</a>
        <a routerLink="/processes" routerLinkActive="active">Processes</a>
      </div>
    </nav>
    <main>
      <router-outlet />
    </main>
  `,
  styles: [`
    .top-nav { display: flex; align-items: center; gap: 32px; padding: 0 24px; height: 56px; background: #1e293b; color: white; }
    .logo { font-weight: 700; font-size: 18px; color: white; text-decoration: none; }
    .nav-links { display: flex; gap: 16px; }
    .nav-links a { color: #94a3b8; text-decoration: none; font-size: 14px; padding: 4px 0; border-bottom: 2px solid transparent; }
    .nav-links a.active { color: white; border-bottom-color: #4f46e5; }
    main { min-height: calc(100vh - 56px); background: #f8fafc; }
  `]
})
export class App {}
