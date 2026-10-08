import { Component, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChakraComponent } from '../../shared/chakra.component';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { I18nService } from '../../core/i18n.service';
import { FlockService } from '../../core/flock.service';

interface Box { x1: number; y1: number; x2: number; y2: number; confidence: number; }

interface CountResponse {
  counted: number;
  range: { low: number; high: number };
  clear: number;
  quality: 'high' | 'medium' | 'low' | 'none';
  crowding: number;
  image: { width: number; height: number };
  boxes: Box[];
  note: string;
  quality_label: string;
  lang: string;
  needs_confirmation: boolean;
  tips: string[] | null;
  /** Video only. Absent for a photo. */
  motion?: 'steady' | 'moving' | 'fast';
  frames_sampled?: number;
  duration_s?: number;
  peak_frame_count?: number;
}

/**
 * Photograph the shed, check the count by eye, correct it if wrong.
 *
 * The design decision that matters: the model's number is never presented as
 * the answer. It fills in a field the farmer edits. Boxes are drawn over the
 * photo so the count can be checked by looking rather than trusted blindly,
 * and the confirmed figure is what gets recorded.
 */
@Component({
  selector: 'app-count',
  standalone: true,
  imports: [ChakraComponent, CommonModule, FormsModule],
  template: `
    <h1 class="title">📷 {{ t()('count.title') }}</h1>
    <div class="card" data-noread><app-chakra flow="count" [compact]="true" [current]="stage()" /></div>

    <div class="card">
      <p class="hint">{{ t()('count.prompt') }}</p>

      <!-- Inputs are driven programmatically. The capture attribute is
           deliberately NOT set: with it, iOS opens the camera only and gives
           no way to pick an existing photo, which is usually what a farmer
           wants. The accept attribute still offers the camera in the sheet. -->
      <input #photoInput type="file" accept="image/*"
             (change)="onFile($event, 'photo')" hidden />
      <input #videoInput type="file" accept="video/*"
             (change)="onFile($event, 'video')" hidden />

      <button type="button" class="pick" [disabled]="busy()"
              (click)="photoInput.click()">
        <span class="pick-ic" aria-hidden="true">📷</span>{{ t()('count.photo') }}
      </button>

      <button type="button" class="pick video" [disabled]="busy()"
              (click)="videoInput.click()">
        <span class="pick-ic" aria-hidden="true">🎥</span>{{ t()('count.video') }}
      </button>
      <div class="hint tiny">{{ t()('count.videoHint') }}</div>

      <div class="err" *ngIf="error()" role="alert">{{ error() }}</div>

      <div class="working" *ngIf="busy()" role="status">
        <span class="spinner"></span>
        <span>{{ mode() === 'video' ? t()('count.watching') : t()('count.counting') }}</span>
      </div>
    </div>

    <div class="card" *ngIf="mode() === 'photo' && preview() as src">
      <div class="frame">
        <img [src]="src" (load)="onImageLoad($event)" alt="" />
        <div class="box" *ngFor="let b of scaledBoxes()"
             [class.sure]="b.confidence >= 0.45"
             [style.left.px]="b.x1" [style.top.px]="b.y1"
             [style.width.px]="b.x2 - b.x1" [style.height.px]="b.y2 - b.y1"></div>
      </div>
      <div class="hint legend" *ngIf="result()" data-noread>
        <span class="k sure"></span> {{ t()('count.sure') }}
        <span class="k"></span> {{ t()('count.unsure') }}
      </div>
    </div>

    <div class="card" *ngIf="result() as r">
      <div class="hero">
        <span class="big">{{ r.counted }}</span>
        <span class="unit">{{ t()('count.found') }}</span>
      </div>

      <div class="qual" [class]="r.quality">
        <b>{{ t()('count.q.' + r.quality) }}</b>
        <span *ngIf="r.range.low !== r.range.high"> ({{ r.range.low }}–{{ r.range.high }})</span>
      </div>

      <div class="vstats" *ngIf="r.frames_sampled">
        <span>{{ t()('count.frames', { n: r.frames_sampled }) }}</span>
        <span *ngIf="r.peak_frame_count as p">{{ t()('count.best', { n: p }) }}</span>
      </div>

      <div class="confirm">
        <label for="confirmed">✍️ {{ t()('count.check') }}</label>
        <div class="stepper">
          <button type="button" (click)="bump(-1)" aria-label="−1">−</button>
          <input id="confirmed" type="number" inputmode="numeric" min="0" [(ngModel)]="confirmed" />
          <button type="button" (click)="bump(1)" aria-label="+1">+</button>
        </div>
        <button type="button" (click)="save()" [disabled]="saving()">✔ {{ t()('count.save') }}</button>
      </div>

      <details *ngIf="r.quality !== 'high'">
        <summary>💡 {{ t()('count.tipsTitle') }}</summary>
        <ul class="tips"><li *ngFor="let i of [1, 2, 3, 4, 5]">{{ t()('count.tip.' + i) }}</li></ul>
      </details>
    </div>

    <div class="ok-box" *ngIf="saved()" role="status">✅ {{ t()('count.saved', { n: confirmed }) }}</div>
  `,
  styles: [`
    .title{margin-top:14px}
    .pick{display:flex;width:100%;margin:12px 0 0;min-height:64px;font-size:19px;cursor:pointer;-webkit-tap-highlight-color:transparent}
    .pick-ic{font-size:26px}
    .pick.video{background:#0F766E}
    .working{display:flex;align-items:center;gap:10px;margin-top:14px;color:var(--muted);font-size:16px}
    .spinner{width:22px;height:22px;border:3px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;flex:none}
    @keyframes spin{to{transform:rotate(360deg)}}
    .tiny{font-size:14px;text-align:center;margin-top:8px}
    .vstats{display:flex;flex-wrap:wrap;gap:12px;color:var(--muted);font-size:15px;margin:8px 0}
    .frame{position:relative;display:inline-block;max-width:100%}
    .frame img{max-width:100%;display:block;border-radius:12px}
    .box{position:absolute;border:2px solid #f0a020;border-radius:3px;pointer-events:none}
    .box.sure{border-color:#16a34a;border-width:3px}
    .legend{display:flex;align-items:center;gap:6px;margin-top:8px;flex-wrap:wrap}
    .k{display:inline-block;width:14px;height:14px;border:2px solid #f0a020;border-radius:3px}
    .k.sure{border-color:#16a34a}
    .hero{display:flex;align-items:baseline;justify-content:center;gap:10px;margin-bottom:8px}
    .hero .big{font-size:64px}
    .hero .unit{color:var(--muted);font-size:20px;font-weight:700}
    .qual{display:block;text-align:center;padding:8px 12px;border-radius:12px;font-size:16px;margin-bottom:8px}
    .qual.high{background:var(--ok-soft);color:#14532d}
    .qual.medium{background:var(--warn-soft);color:#713f12}
    .qual.low,.qual.none{background:var(--bad-soft);color:#7f1d1d}
    .confirm{margin-top:14px;padding-top:14px;border-top:2px solid var(--line)}
    .tips{margin:8px 0 0;padding-left:22px;color:var(--muted);font-size:16px}
    .tips li{margin-bottom:6px}
  `],
})
export class CountComponent {
  private api = inject(ApiService);
  private i18n = inject(I18nService);
  private flock = inject(FlockService);
  t = this.i18n.t;

  preview = signal<string | null>(null);
  mode = signal<'photo' | 'video'>('photo');
  result = signal<CountResponse | null>(null);
  saved = signal<{ message: string; model_note: string; model_proposed: number; difference: number } | null>(null);
  error = signal('');
  busy = signal(false);
  saving = signal(false);
  confirmed = 0;
  /** Where the farmer is on the chakra: pick, counting, check, recorded. */
  stage = computed(() => this.saved() ? 3 : this.result() ? 2 : this.busy() ? 1 : 0);

  /** Displayed image size, so boxes can be scaled from original pixels. */
  private shown = signal<{ w: number; h: number }>({ w: 0, h: 0 });

  /** Boxes in on-screen coordinates. The API returns original-image pixels. */
  scaledBoxes = computed<Box[]>(() => {
    const r = this.result();
    const s = this.shown();
    if (!r || !s.w || !r.image.width) return [];
    const fx = s.w / r.image.width;
    const fy = s.h / r.image.height;
    return r.boxes.map((b) => ({
      x1: b.x1 * fx, y1: b.y1 * fy, x2: b.x2 * fx, y2: b.y2 * fy,
      confidence: b.confidence,
    }));
  });

  onImageLoad(event: Event): void {
    const img = event.target as HTMLImageElement;
    this.shown.set({ w: img.clientWidth, h: img.clientHeight });
  }

  onFile(event: Event, mode: 'photo' | 'video'): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    // Clear it immediately: without this, choosing the same file twice fires
    // no change event and the app looks frozen.
    input.value = '';
    if (!file) return;

    this.mode.set(mode);
    this.error.set('');
    this.result.set(null);
    this.saved.set(null);
    this.preview.set(null);

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      if (mode === 'photo') this.preview.set(dataUrl);
      this.send(dataUrl, mode);
    };
    reader.onerror = () =>
      this.error.set(this.t()('count.readFail'));
    reader.readAsDataURL(file);
  }

  private send(dataUrl: string, mode: 'photo' | 'video'): void {
    this.busy.set(true);
    const path = mode === 'video' ? 'video' : 'photo';
    const lang = this.i18n.lang();
    const body = mode === 'video'
      ? { video_base64: dataUrl, lang }
      : { image_base64: dataUrl, lang };
    this.api.post<CountResponse>('count', path, body)
      .subscribe({
        next: (r) => {
          this.result.set(r);
          this.confirmed = r.counted;
          this.busy.set(false);
        },
        error: (e) => {
          this.error.set(e?.status === 401 ? this.t()('common.netFail') : (e?.error?.detail ?? this.t()('count.fail')));
          this.busy.set(false);
        },
      });
  }

  bump(by: number): void {
    this.confirmed = Math.max(0, (this.confirmed || 0) + by);
  }

  save(): void {
    const r = this.result();
    if (!r) return;
    this.saving.set(true);
    this.api.post<any>('count', 'confirm', {
      counted: r.counted,
      confirmed: this.confirmed,
      lang: this.i18n.lang(),
    }).subscribe({
      next: (s) => { this.saved.set(s); this.saving.set(false); this.flock.recordCount(this.confirmed); },
      error: () => {
        this.error.set(this.t()('count.saveFail'));
        this.saving.set(false);
      },
    });
  }


}
