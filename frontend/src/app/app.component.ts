import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ApiService, FeatureInfo } from './core/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header>
      <div class="wrap">
        <h1>🐔 Poultry 360</h1>
        <div class="sub">मुर्गी पालन सहायक · every answer from a cited source</div>
      </div>
    </header>

    <nav class="wrap" *ngIf="features().length > 1">
      <a *ngFor="let f of features()" [routerLink]="'/' + f.key"
         routerLinkActive="on" class="tab" [class.off]="!f.healthy">
        {{ f.icon }} {{ f.name_hi }}
        <em *ngIf="f.status !== 'live'">{{ f.status }}</em>
      </a>
    </nav>

    <main class="wrap"><router-outlet /></main>
  `,
  styles: [`
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
  features = signal<FeatureInfo[]>([]);

  constructor() {
    // The menu is data, not markup: a new backend feature appears here with
    // no change to this component.
    this.api.features().subscribe({
      next: (r) => this.features.set(r.features),
      error: () => {},
    });
  }
}
