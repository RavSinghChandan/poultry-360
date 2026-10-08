import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AuthService } from './core/auth.service';
import { I18nService } from './core/i18n.service';
import { SpeechService } from './core/speech.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="top" data-noread>
      <div class="wrap bar">
        <a routerLink="/today" class="brand" aria-label="Poultry 360"><span class="logo">🐔</span><span>Poultry 360</span></a>
        <div class="acts">
          <button *ngIf="speech.supported && !bare()" type="button" class="listen" (click)="listen()"
                  [attr.aria-label]="t()(speech.speaking() ? 'common.stop' : 'common.listen')">
            <span aria-hidden="true">{{ speech.speaking() ? '⏹' : '🔊' }}</span><span class="lbl">{{ t()(speech.speaking() ? 'common.stop' : 'common.listen') }}</span>
          </button>
          <a routerLink="/language" class="lang" [attr.aria-label]="t()('common.language')"><span aria-hidden="true">🌐</span> {{ i18n.current()?.native || 'English' }}</a>
        </div>
      </div>
      <div class="wrap farm" *ngIf="auth.session() as s">
        <span>🏡 {{ s.tenantName }}</span>
        <a href="" (click)="$event.preventDefault(); signOut()">{{ t()('common.signOut') }}</a>
      </div>
    </header>

    <main id="main" class="wrap"><router-outlet /></main>

    <nav class="tabs" *ngIf="!bare()" data-noread [attr.aria-label]="'Poultry 360'">
      <a *ngFor="let tab of tabs" [routerLink]="tab.path" routerLinkActive="on" class="tab">
        <span class="ic" aria-hidden="true">{{ tab.icon }}</span><span>{{ t()(tab.label) }}</span>
      </a>
    </nav>
  `,
  styles: [`
    .top{position:sticky;top:0;z-index:20;background:rgba(247,244,238,.95);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
    .bar{display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:62px}
    .brand{display:flex;align-items:center;gap:8px;font-weight:900;font-size:20px;text-decoration:none;color:var(--ink);white-space:nowrap}
    .logo{font-size:26px}
    .acts{display:flex;gap:8px;align-items:center}
    .listen{width:auto;margin:0;min-height:46px;padding:0 14px;font-size:16px;border-radius:999px;background:var(--ink);gap:6px}
    .lang{display:flex;align-items:center;gap:6px;min-height:46px;padding:0 14px;border-radius:999px;border:2px solid var(--line);background:#fff;font-weight:700;font-size:16px;text-decoration:none}
    @media (max-width:440px){.listen .lbl{display:none}.listen{width:46px;padding:0;justify-content:center;font-size:20px}}
    .farm{display:flex;justify-content:space-between;gap:10px;padding-bottom:8px;font-size:15px;font-weight:700;color:var(--muted)}
    .farm a{color:var(--accent)}
    main{padding-top:6px;padding-bottom:24px}
    .tabs{position:fixed;left:0;right:0;bottom:0;z-index:20;display:grid;grid-template-columns:repeat(5,1fr);
          background:#fff;border-top:1px solid var(--line);padding:6px 4px calc(6px + env(safe-area-inset-bottom));box-shadow:0 -8px 24px -16px rgba(0,0,0,.25)}
    .tab{display:flex;flex-direction:column;align-items:center;gap:2px;padding:6px 2px;min-height:60px;border-radius:14px;text-decoration:none;color:var(--muted);font-size:13px;font-weight:700;text-align:center}
    .tab .ic{font-size:26px;line-height:1.1;filter:grayscale(.35)}
    .tab.on{color:var(--accent);background:var(--accent-soft)}
    .tab.on .ic{filter:none}
  `],
})
export class AppComponent {
  i18n = inject(I18nService);
  speech = inject(SpeechService);
  auth = inject(AuthService);
  private router = inject(Router);
  t = this.i18n.t;
  private url = signal(this.router.url);
  /** The language picker and the owner's page get the whole screen. */
  bare = computed(() => /^\/(language|admin)/.test(this.url()));
  readonly tabs = [
    { path: '/today', icon: '🏠', label: 'nav.today' },
    { path: '/count', icon: '📷', label: 'nav.count' },
    { path: '/feed', icon: '🌾', label: 'nav.feed' },
    { path: '/health', icon: '🩺', label: 'nav.health' },
    { path: '/diary', icon: '📒', label: 'nav.diary' },
  ];

  constructor() {
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd)).subscribe((e) => {
      this.url.set((e as NavigationEnd).urlAfterRedirects);
      this.speech.stop();
    });
  }

  listen(): void {
    if (this.speech.speaking()) this.speech.stop();
    else this.speech.readElement(document.getElementById('main'));
  }

  signOut(): void {
    this.auth.logout();
    this.router.navigateByUrl('/welcome');
  }
}
