import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { AuthService } from './auth.service';

export interface Batch { start: string; birds: number; }
export interface DiaryEntry { date: string; deaths: number; feedKg: number | null; counted: number | null; note: string; }
interface FlockData { batch: Batch | null; diary: DiaryEntry[]; }

/**
 * The farm's own flock: when the chicks arrived, how many, and a daily diary.
 * Kept on the phone, per farm, so it works offline and nothing private leaves it.
 * Everything else reads from here: age in days, birds alive, today's feed.
 */
@Injectable({ providedIn: 'root' })
export class FlockService {
  private auth = inject(AuthService);
  private key = computed(() => `poultry360.flock.${this.auth.session()?.tenant ?? 'local'}`);
  readonly data = signal<FlockData>({ batch: null, diary: [] });

  readonly batch = computed(() => this.data().batch);
  readonly diary = computed(() => [...this.data().diary].sort((a, b) => b.date.localeCompare(a.date)));
  readonly ageDays = computed(() => {
    const b = this.batch();
    return b ? Math.max(0, Math.floor((startOfDay(new Date()) - startOfDay(new Date(b.start))) / 86400000)) : null;
  });
  readonly deaths = computed(() => this.data().diary.reduce((n, e) => n + (e.deaths || 0), 0));
  readonly alive = computed(() => {
    const b = this.batch();
    return b ? Math.max(0, b.birds - this.deaths()) : null;
  });
  readonly mortalityPct = computed(() => {
    const b = this.batch();
    return b && b.birds ? Math.round((this.deaths() / b.birds) * 1000) / 10 : 0;
  });
  readonly feedTotalKg = computed(() => Math.round(this.data().diary.reduce((n, e) => n + (e.feedKg || 0), 0) * 10) / 10);

  constructor() {
    effect(() => this.data.set(read(this.key())), { allowSignalWrites: true });
  }

  setBatch(batch: Batch): void {
    this.write({ batch, diary: [] });
  }

  today(): DiaryEntry {
    const date = isoToday();
    return this.data().diary.find((e) => e.date === date) ?? { date, deaths: 0, feedKg: null, counted: null, note: '' };
  }

  saveEntry(entry: DiaryEntry): void {
    const rest = this.data().diary.filter((e) => e.date !== entry.date);
    this.write({ ...this.data(), diary: [...rest, entry] });
  }

  recordCount(counted: number): void {
    this.saveEntry({ ...this.today(), counted });
  }

  private write(next: FlockData): void {
    this.data.set(next);
    try { localStorage.setItem(this.key(), JSON.stringify(next)); } catch { /* storage full or private mode */ }
  }
}

export function isoToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function read(key: string): FlockData {
  try {
    const v = JSON.parse(localStorage.getItem(key) || 'null');
    if (v && Array.isArray(v.diary)) return v;
  } catch { /* corrupt or unavailable */ }
  return { batch: null, diary: [] };
}
