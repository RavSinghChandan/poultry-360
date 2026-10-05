import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';
import { ChakraComponent } from '../shared/chakra.component';
import { FORM_STYLES } from './form.css';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ChakraComponent],
  template: `
    <form class="card" *ngIf="!sent(); else done" (ngSubmit)="submit()">
      <h2>{{ t()('register') }}</h2>
      <app-chakra flow="access" [current]="0" [compact]="true" />
      <label class="f">{{ t()('farm') }}<input name="farm" [(ngModel)]="body.farm" /></label>
      <label class="f">{{ t()('owner') }}<input name="owner" [(ngModel)]="body.owner" autocomplete="name" /></label>
      <label class="f">{{ t()('phone') }}<input name="phone" [(ngModel)]="body.phone" type="tel" inputmode="tel" autocomplete="tel" /></label>
      <label class="f">{{ t()('email') }}<input name="email" [(ngModel)]="body.email" type="email" autocomplete="email" /></label>
      <label class="f">{{ t()('district') }}<input name="district" [(ngModel)]="body.district" /></label>
      <div class="card err" *ngIf="error()" role="alert">{{ error() }}</div>
      <button type="submit" [disabled]="busy() || body.farm.trim().length < 2 || !body.owner.trim() || !(body.phone.trim() || body.email.trim())">
        {{ t()('sendRequest') }}</button>
      <p class="alt">{{ t()('haveKey') }} <a routerLink="/login">{{ t()('signIn') }}</a></p>
    </form>
    <ng-template #done>
      <section class="card" role="status">
        <h2>✅ {{ t()('requestSent') }}</h2>
        <p>{{ t()('requestSentHint') }}</p>
        <app-chakra flow="access" [current]="1" />
      </section>
    </ng-template>
  `,
  styles: [FORM_STYLES],
})
export class RegisterPage {
  private auth = inject(AuthService);
  t = inject(I18nService).t;
  body = { farm: '', owner: '', phone: '', email: '', district: '' };
  busy = signal(false);
  sent = signal(false);
  error = signal('');

  async submit(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      await this.auth.register(this.body);
      this.sent.set(true);
    } catch (e) {
      const d = e instanceof HttpErrorResponse ? e.error?.detail : null;
      this.error.set(typeof d === 'string' ? d : this.t()('netFail'));
    } finally {
      this.busy.set(false);
    }
  }
}
