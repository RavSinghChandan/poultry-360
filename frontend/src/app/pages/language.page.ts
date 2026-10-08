import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { I18nService } from '../core/i18n.service';
import { SpeechService } from '../core/speech.service';

/** Pick a language by its own script. No reading of English needed. */
@Component({
  selector: 'app-language',
  standalone: true,
  imports: [CommonModule],
  template: `
    <h1 class="title">🌐 {{ t()('common.chooseLanguage') }}</h1>
    <p class="hint" *ngIf="i18n.lang() !== 'en'">Choose your language</p>
    <div class="grid">
      <button *ngFor="let l of i18n.available()" type="button" class="lang" [class.on]="l.code === i18n.lang() && i18n.chosen()"
              (click)="pick(l.code)" [attr.lang]="l.code">
        <span class="native">{{ l.native }}</span>
        <span class="en" *ngIf="l.code !== 'en'">{{ l.english }}</span>
      </button>
    </div>
  `,
  styles: [`
    .title{margin-top:18px}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
    .lang{flex-direction:column;gap:2px;margin:0;min-height:92px;background:#fff;color:var(--ink);border:2px solid var(--line);box-shadow:var(--shadow)}
    .lang.on{border-color:var(--accent);background:var(--accent-soft)}
    .native{font-size:26px;font-weight:800}
    .en{font-size:14px;font-weight:600;color:var(--muted)}
  `],
})
export class LanguagePage {
  i18n = inject(I18nService);
  private speech = inject(SpeechService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  t = this.i18n.t;

  async pick(code: string): Promise<void> {
    await this.i18n.set(code);
    this.speech.say(this.t()('common.languageSet'));
    this.router.navigateByUrl(this.route.snapshot.queryParamMap.get('next') || '/today');
  }
}
