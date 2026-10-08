import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChakraComponent } from '../../shared/chakra.component';
import { ApiService, Ration } from '../../core/api.service';
import { FlockService } from '../../core/flock.service';
import { I18nService } from '../../core/i18n.service';

/** Age and number of birds in, today's feed out. Every number from a published table. */
@Component({
  selector: 'app-feed',
  standalone: true,
  imports: [ChakraComponent, CommonModule, FormsModule],
  template: `
    <h1 class="title">🌾 {{ t()('feed.title') }}</h1>
    <div class="card" data-noread><app-chakra flow="feed" [compact]="true" [current]="ration() ? 3 : 0" /></div>

    <div class="err" *ngIf="error()" role="alert">{{ error() }}</div>

    <div class="card result" *ngIf="ration() as r">
      <span class="pill">{{ t()('phase.' + r.phase) }} · {{ t()('common.dayN', { n: r.day }) }}</span>
      <div class="hero">
        <div class="hint">{{ t()('feed.today') }}</div>
        <div class="big">{{ r.feed_total_kg }} <small>{{ t()('common.kg') }}</small></div>
        <div class="hint">{{ t()('feed.perBird', { g: r.feed_per_bird_g }) }}</div>
      </div>
      <p class="note">{{ t()('phase.' + r.phase + '.note') }}</p>
      <details>
        <summary>{{ t()('feed.details') }}</summary>
        <div class="rows">
          <div class="rowline"><span>{{ t()('feed.protein') }}</span><b>{{ r.crude_protein_pct }}%</b></div>
          <div class="rowline"><span>{{ t()('feed.energy') }}</span><b>{{ r.energy_kcal_per_kg }} kcal/kg</b></div>
          <div class="rowline"><span>{{ t()('feed.lysine') }}</span><b>{{ r.lysine_pct }}%</b></div>
          <div class="rowline"><span>{{ t()('feed.methionine') }}</span><b>{{ r.methionine_pct }}%</b></div>
          <div class="rowline"><span>{{ t()('feed.calcium') }}</span><b>{{ r.calcium_pct }}%</b></div>
          <div class="rowline"><span>{{ t()('feed.target') }}</span><b>{{ r.target_weight_g || '—' }} {{ t()('common.g') }}</b></div>
        </div>
      </details>
      <div class="src" data-noread>{{ t()('common.source') }}: {{ r.source.join(' · ') }} [{{ r.dataset_version }}]</div>
    </div>

    <div class="card">
      <h2 *ngIf="ration()">✏️ {{ t()('feed.change') }}</h2>
      <p class="pill" *ngIf="fromFlock">🐥 {{ t()('feed.fromFlock') }}</p>
      <label for="day" class="mt">🐣 {{ t()('feed.age') }}</label>
      <div class="stepper">
        <button type="button" (click)="day = clampDay(day - 1)" aria-label="−1">−</button>
        <input id="day" type="number" inputmode="numeric" min="0" max="42" [(ngModel)]="day" />
        <button type="button" (click)="day = clampDay(day + 1)" aria-label="+1">+</button>
      </div>
      <label for="birds" class="mt">🐔 {{ t()('feed.birds') }}</label>
      <div class="stepper">
        <button type="button" (click)="birds = clampBirds(birds - 100)" aria-label="−100">−</button>
        <input id="birds" type="number" inputmode="numeric" min="1" [(ngModel)]="birds" />
        <button type="button" (click)="birds = clampBirds(birds + 100)" aria-label="+100">+</button>
      </div>
      <button type="button" (click)="lookup()" [disabled]="loading()">{{ loading() ? t()('common.wait') : '🌾 ' + t()('feed.show') }}</button>
    </div>

  `,
  styles: [`
    .title{margin-top:14px} .mt{margin-top:14px}
    .hero{text-align:center;margin:14px 0 4px}
    .hero .big small{font-size:24px}
  `],
})
export class FeedComponent {
  private api = inject(ApiService);
  private flock = inject(FlockService);
  t = inject(I18nService).t;
  fromFlock = this.flock.ageDays() !== null && (this.flock.ageDays() ?? 99) <= 42;
  day = this.fromFlock ? this.flock.ageDays()! : 17;
  birds = this.fromFlock ? this.flock.alive() || 1000 : 1000;
  ration = signal<Ration | null>(null);
  error = signal<string>('');
  loading = signal(false);

  constructor() { this.lookup(); }

  clampDay(n: number): number { return Math.min(42, Math.max(0, Math.round(n || 0))); }
  clampBirds(n: number): number { return Math.max(1, Math.round(n || 0)); }

  lookup(): void {
    this.day = this.clampDay(this.day);
    this.birds = this.clampBirds(this.birds);
    this.loading.set(true);
    this.error.set('');
    this.api.post<{ ok: boolean; data?: Ration; error?: string }>('feed', 'ration', { day: this.day, birds: this.birds })
      .subscribe({
        next: (res) => {
          if (res.ok && res.data) this.ration.set(res.data);
          else { this.error.set(this.t()('feed.notFound')); this.ration.set(null); }
          this.loading.set(false);
        },
        error: (e) => {
          this.error.set(e?.status === 429 ? (e.error?.detail ?? this.t()('common.netFail')) : this.t()('common.netFail'));
          this.loading.set(false);
        },
      });
  }
}
