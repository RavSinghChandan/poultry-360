import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from './core/auth.service';
import { ApiService, FeatureInfo } from './core/api.service';
import { I18nService } from './core/i18n.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header>
      <div class="wrap">
        <div class="top">
          <h1><a routerLink="/welcome" class="home">🐔 Poultry 360</a></h1>
          <select class="lang"
                  (change)="pick($any($event.target).value)"
                  [attr.aria-label]="i18n.t()('language')">
            <!-- [selected] rather than [value] on the select: the options are
                 rendered by *ngFor, so a value bound before they exist is
                 dropped and the picker falls back to showing the first entry
                 even though the app is running in the saved language. -->
            <option *ngFor="let l of i18n.available()" [value]="l.code"
                    [selected]="l.code === i18n.lang()">
              {{ l.native }}
            </option>
          </select>
        </div>
        <div class="sub">
          <span>every answer from a cited source</span>
          <span class="who" *ngIf="auth.session() as s">
            {{ i18n.t()('farmOf') }} · {{ s.tenantName }}
            <a href="" (click)="$event.preventDefault(); signOut()">{{ i18n.t()('signOut') }}</a>
          </span>
          <a class="who" *ngIf="!auth.session()" routerLink="/login">{{ i18n.t()('signIn') }}</a>
        </div>
      </div>
    </header>

    <nav class="wrap" *ngIf="features().length > 1">
      <a *ngFor="let f of features()" [routerLink]="'/' + f.key"
         routerLinkActive="on" class="tab" [class.off]="!f.healthy">
        {{ f.icon }} {{ f.name }}
        <em *ngIf="f.status !== 'live'">{{ f.status }}</em>
      </a>
    </nav>

    <main class="wrap"><router-outlet /></main>
  `,
  styles: [`
    .home{color:#fff;text-decoration:none}
    .sub{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
    .who{font-weight:700;color:#fff}
    .who a,a.who{color:#fff;margin-left:8px}
    .top{display:flex;align-items:center;justify-content:space-between;gap:12px}
    .lang{background:rgba(255,255,255,.18);color:#fff;border:1px solid rgba(255,255,255,.45);
          border-radius:10px;padding:8px 10px;font-size:16px;font-weight:600;
          min-height:44px}
    .lang option{color:#111}
    nav{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
    .tab{flex:1;min-width:140px;text-align:center;padding:12px;border-radius:12px;
         background:#fff;border:2px solid var(--line);color:var(--ink);
         text-decoration:none;font-weight:700;font-size:16px}
    .tab.on{border-color:var(--accent);background:var(--accent-soft);color:var(--accent)}
    .tab.off{opacity:.5}
    .tab em{display:block;font-size:12px;font-weight:400;color:var(--muted);font-style:normal}
  `],
})
export class AppComponent {
  private api = inject(ApiService);
  i18n = inject(I18nService);
  features = signal<FeatureInfo[]>([]);
  auth = inject(AuthService);
  private router = inject(Router);

  signOut(): void {
    this.auth.logout();
    this.router.navigateByUrl('/welcome');
  }

  pick(code: string): void {
    this.i18n.set(code);
    this.load();           // menu labels come from the server, so re-fetch
  }

  private load(): void {
    this.api.features(this.i18n.lang()).subscribe({
      next: (r) => this.features.set(r.features),
      error: () => {},
    });
  }

  constructor() {
    // The menu is data, not markup: a new backend feature appears here with
    // no change to this component, and its label arrives already translated.
    this.load();
  }
}
