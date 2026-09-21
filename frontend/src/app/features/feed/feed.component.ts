import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, Ration } from '../../core/api.service';

@Component({
  selector: 'app-feed',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="card">
      <label for="day">मुर्गी की उम्र <span class="hint">(Age in days · 0–42)</span></label>
      <input id="day" type="number" inputmode="numeric" min="0" max="42" [(ngModel)]="day" />

      <label for="birds" class="mt">कितनी मुर्गियाँ <span class="hint">(How many birds)</span></label>
      <input id="birds" type="number" inputmode="numeric" min="1" [(ngModel)]="birds" />

      <button (click)="lookup()" [disabled]="loading()">
        {{ loading() ? 'देख रहे हैं…' : 'आहार बताएँ · Get ration' }}
      </button>
    </div>

    <div class="card err" *ngIf="error()">{{ error() }}</div>

    <div class="card" *ngIf="ration() as r">
      <span class="pill">{{ r.phase_name_hi }} · {{ r.phase_name_en }} (दिन {{ r.day }})</span>
      <div class="hint mt">प्रोटीन · Crude protein</div>
      <div class="big">{{ r.crude_protein_pct }}%</div>

      <div class="rows">
        <div class="row"><span>ऊर्जा · Energy</span><b>{{ r.energy_kcal_per_kg }} kcal/kg</b></div>
        <div class="row"><span>लाइसिन · Lysine</span><b>{{ r.lysine_pct }}%</b></div>
        <div class="row"><span>मेथियोनीन · Methionine</span><b>{{ r.methionine_pct }}%</b></div>
        <div class="row"><span>कैल्शियम · Calcium</span><b>{{ r.calcium_pct }}%</b></div>
        <div class="row"><span>प्रति मुर्गी · Per bird</span><b>{{ r.feed_per_bird_g }} g</b></div>
        <div class="row"><span>कुल आज · Total today</span><b>{{ r.feed_total_kg }} kg</b></div>
        <div class="row"><span>लक्ष्य वज़न · Target</span><b>{{ r.target_weight_g || '—' }} g</b></div>
      </div>

      <div class="note">{{ r.note_hi }} {{ r.note_en }}</div>
      <div class="src">स्रोत · Source: {{ r.source.join(' · ') }} [{{ r.dataset_version }}]</div>
    </div>
  `,
  styles: [`
    .mt{margin-top:16px}
    .rows{margin-top:16px}
    .row{display:flex;justify-content:space-between;align-items:baseline;
         padding:12px 0;border-bottom:1px solid var(--line)}
    .row:last-child{border-bottom:0}
    .row span{color:var(--muted);font-size:16px}
    .row b{font-size:20px}
  `],
})
export class FeedComponent {
  private api = inject(ApiService);
  day = 17;
  birds = 1000;
  ration = signal<Ration | null>(null);
  error = signal<string>('');
  loading = signal(false);

  constructor() { this.lookup(); }

  lookup(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.post<{ ok: boolean; data?: Ration; error?: string }>(
      'feed', 'ration', { day: this.day, birds: this.birds },
    ).subscribe({
      next: (res) => {
        if (res.ok && res.data) { this.ration.set(res.data); }
        else { this.error.set(res.error || 'नहीं मिला'); this.ration.set(null); }
        this.loading.set(false);
      },
      error: () => {
        this.error.set('सर्वर नहीं मिला · Backend not reachable on port 8000.');
        this.loading.set(false);
      },
    });
  }
}
