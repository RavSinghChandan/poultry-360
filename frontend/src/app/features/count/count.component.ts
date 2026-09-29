import { Component, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { I18nService } from '../../core/i18n.service';

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
  imports: [CommonModule, FormsModule],
  template: `
    <div class="card">
      <div class="hint">{{ t()('prompt') }}</div>

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
        {{ t()('takePhoto') }}
      </button>

      <button type="button" class="pick video" [disabled]="busy()"
              (click)="videoInput.click()">
        {{ t()('recordVideo') }}
      </button>
      <div class="hint tiny">{{ t()('videoFindsMore') }}</div>

      <div class="err" *ngIf="error()">{{ error() }}</div>

      <div class="working" *ngIf="busy()">
        <span class="spinner"></span>
        <span>{{ mode() === 'video' ? t()('watching') : t()('counting') }}</span>
      </div>
    </div>

    <div class="card" *ngIf="mode() === 'photo' && preview() as src">
      <div class="frame">
        <img [src]="src" (load)="onImageLoad($event)" alt="flock" />
        <div class="box" *ngFor="let b of scaledBoxes()"
             [class.sure]="b.confidence >= 0.45"
             [style.left.px]="b.x1" [style.top.px]="b.y1"
             [style.width.px]="b.x2 - b.x1" [style.height.px]="b.y2 - b.y1"></div>
      </div>
      <div class="hint legend" *ngIf="result()">
        <span class="k sure"></span> {{ t()('clear') }}
        <span class="k"></span> {{ t()('uncertain') }}
      </div>
    </div>

    <div class="card" *ngIf="result() as r">
      <div class="big">
        <span class="n">{{ r.counted }}</span>
        <span class="unit">{{ t()('birdsFound') }}</span>
      </div>

      <div class="qual" [class]="r.quality">
        <b>{{ r.quality_label }}</b>
        <span *ngIf="r.range.low !== r.range.high">
          ({{ r.range.low }}–{{ r.range.high }})
        </span>
      </div>

      <div class="vstats" *ngIf="r.frames_sampled">
        <span>{{ r.frames_sampled }} {{ t()('framesChecked') }}</span>
        <span *ngIf="r.peak_frame_count as p">{{ t()('bestFrame') }} {{ p }}</span>
      </div>

      <p class="note">{{ r.note }}</p>

      <div class="confirm">
        <div class="hint">{{ t()('enterCorrect') }}</div>
        <div class="row">
          <button (click)="bump(-1)" aria-label="less">−</button>
          <input type="number" min="0" [(ngModel)]="confirmed" />
          <button (click)="bump(1)" aria-label="more">+</button>
        </div>
        <button class="save" (click)="save()" [disabled]="saving()">
          {{ t()('recordNumber') }}
        </button>
      </div>

      <ul class="tips" *ngIf="r.tips as tipList">
        <li *ngFor="let tip of tipList">{{ tip }}</li>
      </ul>
    </div>

    <div class="card ok" *ngIf="saved() as s">
      <b>{{ s.message }}</b>
      <div class="hint" *ngIf="s.difference !== 0">{{ s.model_note }}</div>
    </div>
  `,
  styles: [`
    .pick{display:block;width:100%;margin:12px 0;text-align:center;
          background:var(--accent);color:#fff;border:0;
          padding:18px;border-radius:12px;font-size:18px;font-weight:600;
          min-height:56px;cursor:pointer;-webkit-tap-highlight-color:transparent}
    .pick:active{transform:scale(.98)}
    .pick:disabled{opacity:.55}
    .pick.video{background:#0f766e}
    .working{display:flex;align-items:center;gap:10px;margin-top:12px;
             color:var(--muted);font-size:15px}
    .spinner{width:20px;height:20px;border:3px solid var(--line);
             border-top-color:var(--accent);border-radius:50%;
             animation:spin .8s linear infinite;flex:none}
    @keyframes spin{to{transform:rotate(360deg)}}
    .tiny{font-size:13px;text-align:center;margin-top:-4px}
    .vstats{display:flex;flex-wrap:wrap;gap:12px;color:var(--muted);font-size:14px;
            margin:8px 0}
    .frame{position:relative;display:inline-block;max-width:100%}
    .frame img{max-width:100%;display:block;border-radius:10px}
    .box{position:absolute;border:2px solid #f0a020;border-radius:3px;pointer-events:none}
    .box.sure{border-color:#16a34a;border-width:3px}
    .legend{display:flex;align-items:center;gap:6px;margin-top:8px;flex-wrap:wrap}
    .k{display:inline-block;width:14px;height:14px;border:2px solid #f0a020;border-radius:3px}
    .k.sure{border-color:#16a34a}
    .big{display:flex;align-items:baseline;gap:10px;margin-bottom:6px}
    .big .n{font-size:52px;font-weight:700;line-height:1}
    .big .unit{color:var(--muted)}
    .qual{display:inline-block;padding:6px 10px;border-radius:8px;font-size:14px;margin-bottom:8px}
    .qual.high{background:#dcfce7;color:#14532d}
    .qual.medium{background:#fef3c7;color:#713f12}
    .qual.low,.qual.none{background:#fee2e2;color:#7f1d1d}
    .note{margin:10px 0}
    .confirm{margin-top:14px;padding-top:14px;border-top:2px solid var(--line)}
    .row{display:flex;gap:10px;align-items:center;margin:10px 0}
    .row button{width:56px;height:56px;font-size:26px;border-radius:12px;
                border:2px solid var(--line);background:#fff;color:var(--ink)}
    .row input{flex:1;font-size:30px;text-align:center;padding:10px;
               border:2px solid var(--line);border-radius:12px;min-width:0}
    .save{width:100%;padding:16px;font-size:18px}
    .tips{margin:12px 0 0;padding-left:20px;color:var(--muted);font-size:14px}
    .err{background:#fee2e2;color:#7f1d1d;padding:12px;border-radius:10px;margin-top:10px}
    .ok{border-color:#16a34a}
  `],
})
export class CountComponent {
  private api = inject(ApiService);
  private i18n = inject(I18nService);
  t = this.i18n.t;

  preview = signal<string | null>(null);
  mode = signal<'photo' | 'video'>('photo');
  result = signal<CountResponse | null>(null);
  saved = signal<{ message: string; model_note: string; model_proposed: number; difference: number } | null>(null);
  error = signal('');
  busy = signal(false);
  saving = signal(false);
  confirmed = 0;

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
      this.error.set(this.t()('readFail'));
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
          this.error.set(e?.error?.detail ?? this.t()('countFail'));
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
      next: (s) => { this.saved.set(s); this.saving.set(false); },
      error: () => {
        this.error.set(this.t()('saveFail'));
        this.saving.set(false);
      },
    });
  }


}
