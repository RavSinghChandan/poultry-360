import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChakraComponent } from '../../shared/chakra.component';
import { ApiService } from '../../core/api.service';

interface Sign { key: string; en: string; hi: string; suggests_en: string; suggests_hi: string; }

@Component({
  selector: 'app-health',
  standalone: true,
  imports: [ChakraComponent, CommonModule],
  template: `
    <div class="card"><app-chakra flow="health" [compact]="true" [current]="note() ? 2 : picked().size ? 1 : 0" /></div>
    <div class="card">
      <div class="hint">जो दिख रहा है चुनें · Select what you see</div>
      <div class="signs">
        <button class="sign" *ngFor="let s of signs()"
                [class.on]="picked().has(s.key)"
                (click)="toggle(s.key)">
          <b>{{ s.hi }}</b><span>{{ s.en }}</span>
        </button>
      </div>
      <button (click)="assess()" [disabled]="!picked().size">
        सलाह देखें · Get guidance
      </button>
    </div>

    <div class="card" *ngIf="matched().length">
      <div *ngFor="let m of matched()" class="note">
        <b>{{ m.hi }}</b><br />{{ m.suggests_hi }}<br />
        <span class="hint">{{ m.suggests_en }}</span>
      </div>
      <div class="src">{{ note() }}</div>
    </div>
  `,
  styles: [`
    .signs{display:grid;gap:10px;margin:14px 0}
    .sign{display:flex;flex-direction:column;align-items:flex-start;gap:2px;
          background:#fff;color:var(--ink);border:2px solid var(--line);
          padding:14px;border-radius:12px;font-size:17px;text-align:left}
    .sign.on{border-color:var(--accent);background:var(--accent-soft)}
    .sign span{color:var(--muted);font-size:14px;font-weight:400}
  `],
})
export class HealthComponent {
  private api = inject(ApiService);
  signs = signal<Sign[]>([]);
  picked = signal<Set<string>>(new Set());
  matched = signal<Sign[]>([]);
  note = signal('');

  constructor() {
    this.api.get<{ data: Sign[] }>('health', 'signs')
      .subscribe({ next: (r) => this.signs.set(r.data), error: () => {} });
  }

  toggle(key: string): void {
    const next = new Set(this.picked());
    next.has(key) ? next.delete(key) : next.add(key);
    this.picked.set(next);
  }

  assess(): void {
    this.api.post<{ matched: Sign[]; note_hi: string; note_en: string }>(
      'health', 'assess', { signs: [...this.picked()] },
    ).subscribe({
      next: (r) => { this.matched.set(r.matched); this.note.set(r.note_hi + ' ' + r.note_en); },
      error: () => {},
    });
  }
}
