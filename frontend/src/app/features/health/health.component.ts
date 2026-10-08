import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChakraComponent } from '../../shared/chakra.component';
import { ApiService } from '../../core/api.service';
import { FlockService } from '../../core/flock.service';
import { I18nService } from '../../core/i18n.service';

/** Signs a farmer can see, matched to general guidance. Never a diagnosis. */
const SIGN_ICONS: Record<string, string> = {
  huddling: '🥶', panting: '🥵', loose_droppings: '💩', not_eating: '🍽️',
  noisy_breathing: '😮‍💨', lame: '🦵', sudden_deaths: '⚠️',
};

@Component({
  selector: 'app-health',
  standalone: true,
  imports: [ChakraComponent, CommonModule],
  template: `
    <h1 class="title">🩺 {{ t()('health.title') }}</h1>
    <div class="card" data-noread><app-chakra flow="health" [compact]="true" [current]="matched().length ? 2 : picked().size ? 1 : 0" /></div>

    <div class="card">
      <h2>{{ t()('health.prompt') }}</h2>
      <div class="tiles">
        <button type="button" class="tile" *ngFor="let k of keys()" [class.on]="picked().has(k)" (click)="toggle(k)" [attr.aria-pressed]="picked().has(k)">
          <span class="ic">{{ icon(k) }}</span>{{ t()('health.sign.' + k) }}
        </button>
      </div>
      <button type="button" (click)="assess()" [disabled]="!picked().size || loading()">{{ loading() ? t()('common.wait') : '✔ ' + t()('health.show') }}</button>
    </div>

    <div class="err" *ngIf="error()" role="alert">{{ error() }}</div>

    <div class="card" *ngIf="matched().length">
      <div class="advice" *ngFor="let k of matched()" [class.urgent]="k === 'sudden_deaths'">
        <b>{{ icon(k) }} {{ t()('health.sign.' + k) }}</b>
        <p>{{ t()('health.advice.' + k) }}</p>
      </div>
      <div class="note vet">📞 {{ t()('health.vet') }}</div>
    </div>
  `,
  styles: [`
    .title{margin-top:14px}
    .tile{font-size:16px;min-height:112px}
    .advice{padding:12px 0;border-bottom:1px solid var(--line)}
    .advice:last-of-type{border-bottom:0}
    .advice p{margin:4px 0 0}
    .advice.urgent b{color:var(--bad)}
    .vet{border-left-color:var(--bad);font-weight:700}
  `],
})
export class HealthComponent {
  private api = inject(ApiService);
  private flock = inject(FlockService);
  t = inject(I18nService).t;
  keys = signal<string[]>(Object.keys(SIGN_ICONS));
  picked = signal<Set<string>>(new Set());
  matched = signal<string[]>([]);
  loading = signal(false);
  error = signal('');

  constructor() {
    // the server is the source of truth for which signs exist
    this.api.get<{ data: { key: string }[] }>('health', 'signs').subscribe({
      next: (r) => this.keys.set(r.data.map((s) => s.key)),
      error: () => {},
    });
  }

  icon(k: string): string { return SIGN_ICONS[k] ?? '•'; }

  toggle(key: string): void {
    const next = new Set(this.picked());
    next.has(key) ? next.delete(key) : next.add(key);
    this.picked.set(next);
  }

  assess(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.post<{ matched: { key: string }[] }>('health', 'assess', { signs: [...this.picked()], day: (this.flock.ageDays() ?? 99) <= 60 ? this.flock.ageDays() : undefined })
      .subscribe({
        next: (r) => { this.matched.set(r.matched.map((m) => m.key)); this.loading.set(false); },
        error: () => { this.error.set(this.t()('common.netFail')); this.loading.set(false); },
      });
  }
}
