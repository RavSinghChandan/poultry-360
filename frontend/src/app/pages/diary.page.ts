import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { DiaryEntry, FlockService } from '../core/flock.service';
import { I18nService } from '../core/i18n.service';

/** One page a day: birds that died, feed used, the count, a note. */
@Component({
  selector: 'app-diary',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <h1 class="title">📒 {{ t()('diary.title') }}</h1>

    <section class="card" *ngIf="!flock.batch()">
      <p>{{ t()('diary.needBatch') }}</p>
      <a class="btn" routerLink="/today">➕ {{ t()('today.addBatch') }}</a>
    </section>

    <section class="card" *ngIf="flock.batch()">
      <h2>{{ t()('diary.today') }} · {{ t()('common.dayN', { n: flock.ageDays() ?? 0 }) }}</h2>
      <label for="deaths">💀 {{ t()('diary.deaths') }}</label>
      <div class="stepper">
        <button type="button" (click)="entry.deaths = max0(entry.deaths - 1)" aria-label="−1">−</button>
        <input id="deaths" type="number" inputmode="numeric" min="0" [(ngModel)]="entry.deaths" />
        <button type="button" (click)="entry.deaths = max0(entry.deaths + 1)" aria-label="+1">+</button>
      </div>
      <label for="feed" class="mt">🌾 {{ t()('diary.feedUsed') }}</label>
      <div class="stepper">
        <button type="button" (click)="entry.feedKg = max0((entry.feedKg || 0) - 5)" aria-label="−5">−</button>
        <input id="feed" type="number" inputmode="decimal" min="0" [(ngModel)]="entry.feedKg" />
        <button type="button" (click)="entry.feedKg = max0((entry.feedKg || 0) + 5)" aria-label="+5">+</button>
      </div>
      <label for="note" class="mt">✍️ {{ t()('diary.note') }}</label>
      <input id="note" type="text" [(ngModel)]="entry.note" [placeholder]="t()('diary.notePlaceholder')" />
      <p class="hint mt" *ngIf="entry.counted">📷 {{ t()('diary.counted', { n: entry.counted }) }}</p>
      <button type="button" (click)="save()">✔ {{ t()('diary.save') }}</button>
      <div class="ok-box" *ngIf="saved()" role="status">✅ {{ t()('diary.saved') }}</div>
    </section>

    <section class="card" *ngIf="flock.batch()">
      <h2>{{ t()('diary.summary') }}</h2>
      <div class="stat-row">
        <div class="stat"><b>{{ flock.alive() }}</b><span>{{ t()('today.alive') }}</span></div>
        <div class="stat"><b>{{ flock.deaths() }}</b><span>{{ t()('diary.deathsTotal') }}</span></div>
        <div class="stat"><b>{{ flock.mortalityPct() }}%</b><span>{{ t()('diary.mortality') }}</span></div>
      </div>
      <p class="hint mt">🌾 {{ t()('diary.feedTotal', { n: flock.feedTotalKg() }) }}</p>
    </section>

    <section class="card" *ngIf="flock.diary().length">
      <h2>{{ t()('diary.history') }}</h2>
      <div class="rows">
        <div class="rowline" *ngFor="let e of flock.diary()">
          <span>{{ e.date | date: 'd MMM' }}</span>
          <b>💀 {{ e.deaths }} · 🌾 {{ e.feedKg ?? '—' }} {{ t()('common.kg') }}<ng-container *ngIf="e.counted"> · 📷 {{ e.counted }}</ng-container></b>
        </div>
      </div>
    </section>
  `,
  styles: [`.title{margin-top:14px} .mt{margin-top:14px}`],
})
export class DiaryPage {
  flock = inject(FlockService);
  t = inject(I18nService).t;
  entry: DiaryEntry = { ...this.flock.today() };
  saved = signal(false);

  max0(n: number): number { return Math.max(0, Math.round((n || 0) * 10) / 10); }

  save(): void {
    this.flock.saveEntry({ ...this.entry, deaths: Math.max(0, Math.round(this.entry.deaths || 0)), feedKg: this.entry.feedKg ? this.max0(this.entry.feedKg) : null });
    this.saved.set(true);
    setTimeout(() => this.saved.set(false), 2500);
  }
}
