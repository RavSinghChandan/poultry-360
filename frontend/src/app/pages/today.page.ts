import { Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService, Ration } from '../core/api.service';
import { FlockService, isoToday } from '../core/flock.service';
import { I18nService } from '../core/i18n.service';

/** The farm at a glance: how old the birds are, how many are alive, feed for today. */
@Component({
  selector: 'app-today',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <h1 class="hello">{{ t()('today.title') }}</h1>

    <section class="card flock" *ngIf="flock.batch() as b; else setup">
      <div class="head">
        <h2>🐥 {{ t()('batch.title') }}</h2>
        <button type="button" class="quiet small" (click)="editing.set(true)" data-noread>✏️ {{ t()('batch.edit') }}</button>
      </div>
      <div class="stat-row">
        <div class="stat"><b>{{ flock.ageDays() }}</b><span>{{ t()('today.ageDays') }}</span></div>
        <div class="stat"><b>{{ flock.alive() }}</b><span>{{ t()('today.alive') }}</span></div>
        <div class="stat"><b>{{ ration()?.feed_total_kg ?? '—' }}</b><span>{{ t()('today.feedKg') }}</span></div>
      </div>
      <p class="hint line" *ngIf="flock.deaths()">{{ t()('today.deathsSoFar', { n: flock.deaths(), pct: flock.mortalityPct() }) }}</p>
      <p class="hint line" *ngIf="(flock.ageDays() ?? 0) > 42">{{ t()('today.pastCycle') }}</p>
    </section>

    <ng-template #setup>
      <section class="card">
        <h2>🐥 {{ t()('today.noBatch') }}</h2>
        <p class="hint">{{ t()('today.noBatchHint') }}</p>
        <button type="button" (click)="editing.set(true)">➕ {{ t()('today.addBatch') }}</button>
      </section>
    </ng-template>

    <section class="card" *ngIf="editing()">
      <h2>{{ t()('batch.title') }}</h2>
      <label for="start">📅 {{ t()('batch.start') }}</label>
      <input id="start" type="date" [(ngModel)]="start" [max]="todayIso" />
      <label for="birds" class="mt">🐥 {{ t()('batch.birds') }}</label>
      <div class="stepper">
        <button type="button" (click)="birds = clamp(birds - 100)" aria-label="−100">−</button>
        <input id="birds" type="number" inputmode="numeric" min="1" [(ngModel)]="birds" />
        <button type="button" (click)="birds = clamp(birds + 100)" aria-label="+100">+</button>
      </div>
      <p class="hint" *ngIf="flock.batch()">{{ t()('batch.newWarning') }}</p>
      <button type="button" (click)="saveBatch()" [disabled]="!start || birds < 1">✔ {{ t()('batch.save') }}</button>
      <button type="button" class="quiet" (click)="editing.set(false)">{{ t()('common.cancel') }}</button>
    </section>

    <h2 class="ask">{{ t()('today.whatToDo') }}</h2>
    <div class="tiles">
      <a class="tile" routerLink="/count"><span class="ic">📷</span>{{ t()('today.goCount') }}</a>
      <a class="tile" routerLink="/feed"><span class="ic">🌾</span>{{ t()('today.goFeed') }}</a>
      <a class="tile" routerLink="/health"><span class="ic">🩺</span>{{ t()('today.goHealth') }}</a>
      <a class="tile" routerLink="/diary"><span class="ic">📒</span>{{ t()('today.goDiary') }}</a>
    </div>
  `,
  styles: [`
    .hello{margin-top:14px}
    .head{display:flex;justify-content:space-between;align-items:center;gap:8px}
    .head h2{margin:0}
    .small{width:auto;margin:0;min-height:44px;padding:0 14px;font-size:15px}
    .line{margin:10px 0 0}
    .mt{margin-top:14px}
    .ask{margin-top:22px;font-size:20px}
  `],
})
export class TodayPage {
  flock = inject(FlockService);
  private api = inject(ApiService);
  t = inject(I18nService).t;
  editing = signal(false);
  ration = signal<Ration | null>(null);
  todayIso = isoToday();
  start = this.flock.batch()?.start ?? isoToday();
  birds = this.flock.batch()?.birds ?? 1000;
  private ageAndBirds = computed(() => [this.flock.ageDays(), this.flock.alive()] as const);

  constructor() {
    // the flock loads from the phone after the page starts; follow it
    effect(() => { this.ageAndBirds(); untracked(() => this.loadRation()); });
  }

  clamp(n: number): number { return Math.max(1, Math.round(n || 0)); }

  saveBatch(): void {
    this.flock.setBatch({ start: this.start, birds: this.clamp(this.birds) });
    this.editing.set(false);
  }

  /** Today's feed comes from the same published table as the Feed tab. */
  private loadRation(): void {
    const [age, alive] = this.ageAndBirds();
    if (age === null || !alive || age > 42) { this.ration.set(null); return; }
    this.api.post<{ ok: boolean; data?: Ration }>('feed', 'ration', { day: age, birds: alive })
      .subscribe({ next: (r) => this.ration.set(r.ok && r.data ? r.data : null), error: () => this.ration.set(null) });
  }
}
