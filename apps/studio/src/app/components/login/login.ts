import { Component, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="auth-page">
      <div class="auth-card card">
        <div class="auth-logo">
          <span class="logo-icon">F</span>
          <span class="logo-text">FlowtTix</span>
        </div>

        @if (mode === 'login') {
          <h2>Sign in</h2>
          <p class="subtitle">Enter your credentials to access the studio</p>
          <div class="form-field">
            <label>Email</label>
            <input type="email" [(ngModel)]="email" placeholder="you@example.com" (keydown.enter)="login()" />
          </div>
          <div class="form-field">
            <label>Password</label>
            <input type="password" [(ngModel)]="password" placeholder="Your password" (keydown.enter)="login()" />
          </div>
          @if (error) { <p class="error-msg">{{ error }}</p> }
          <button class="btn-primary full-width" (click)="login()" [disabled]="loading">
            {{ loading ? 'Signing in...' : 'Sign in' }}
          </button>
          <p class="switch-text">
            No account? <a (click)="mode = 'register'; error = ''" class="link">Create one</a>
          </p>
        } @else {
          <h2>Create account</h2>
          <p class="subtitle">Register a new FlowtTix account</p>
          <div class="form-field">
            <label>Name</label>
            <input [(ngModel)]="name" placeholder="Your name" (keydown.enter)="register()" />
          </div>
          <div class="form-field">
            <label>Email</label>
            <input type="email" [(ngModel)]="email" placeholder="you@example.com" (keydown.enter)="register()" />
          </div>
          <div class="form-field">
            <label>Password</label>
            <input type="password" [(ngModel)]="password" placeholder="Min. 8 characters" (keydown.enter)="register()" />
          </div>
          <div class="form-field">
            <label>Role</label>
            <select [(ngModel)]="role">
              <option value="operator">Operator</option>
              <option value="developer">Developer</option>
              <option value="admin">Admin</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>
          @if (error) { <p class="error-msg">{{ error }}</p> }
          <button class="btn-primary full-width" (click)="register()" [disabled]="loading">
            {{ loading ? 'Creating...' : 'Create account' }}
          </button>
          <p class="switch-text">
            Already have an account? <a (click)="mode = 'login'; error = ''" class="link">Sign in</a>
          </p>
        }
      </div>
    </div>
  `,
  styles: [`
    .auth-page {
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; background: var(--bg-secondary);
    }
    .auth-card { width: 380px; padding: 32px; }
    .auth-logo { display: flex; align-items: center; gap: 10px; margin-bottom: 24px; }
    .logo-icon {
      width: 32px; height: 32px; background: var(--color-indigo);
      border-radius: var(--radius-md); display: flex; align-items: center;
      justify-content: center; font-weight: 800; font-size: 16px; color: white;
    }
    .logo-text { font-weight: 700; font-size: 18px; }
    h2 { margin-bottom: 4px; }
    .subtitle { color: var(--text-muted); font-size: 13px; margin-bottom: 20px; }
    .form-field { margin-bottom: 14px; }
    .form-field label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--text-muted); margin-bottom: 4px; font-weight: 600; }
    .form-field input, .form-field select { width: 100%; }
    .full-width { width: 100%; margin-top: 8px; }
    .error-msg { color: var(--color-red); font-size: 13px; margin-bottom: 8px; }
    .switch-text { text-align: center; font-size: 13px; color: var(--text-muted); margin-top: 16px; }
    .link { color: var(--color-indigo); cursor: pointer; font-weight: 500; }
    .link:hover { text-decoration: underline; }
  `]
})
export class LoginComponent {
  mode: 'login' | 'register' = 'login';
  email = '';
  password = '';
  name = '';
  role = 'operator';
  error = '';
  loading = false;

  constructor(private api: ApiService, private router: Router, private cdr: ChangeDetectorRef) {}

  login() {
    if (!this.email || !this.password) { this.error = 'Email and password required'; return; }
    this.loading = true;
    this.error = '';
    this.api.login(this.email, this.password).subscribe({
      next: res => {
        localStorage.setItem('flowtix_token', res.access_token);
        localStorage.setItem('flowtix_user', JSON.stringify(res.user));
        this.router.navigate(['/']);
      },
      error: err => {
        this.error = err.error?.detail || 'Login failed';
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }

  register() {
    if (!this.name || !this.email || !this.password) { this.error = 'All fields required'; return; }
    if (this.password.length < 8) { this.error = 'Password must be at least 8 characters'; return; }
    this.loading = true;
    this.error = '';
    this.api.register(this.email, this.name, this.password, this.role).subscribe({
      next: () => {
        this.api.login(this.email, this.password).subscribe({
          next: res => {
            localStorage.setItem('flowtix_token', res.access_token);
            localStorage.setItem('flowtix_user', JSON.stringify(res.user));
            this.router.navigate(['/']);
          },
          error: () => {
            this.mode = 'login';
            this.error = 'Account created. Please sign in.';
            this.loading = false;
            this.cdr.detectChanges();
          }
        });
      },
      error: err => {
        this.error = err.error?.detail || 'Registration failed';
        this.loading = false;
        this.cdr.detectChanges();
      }
    });
  }
}
