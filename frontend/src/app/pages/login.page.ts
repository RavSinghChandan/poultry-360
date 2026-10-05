import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';
import { ChakraComponent } from '../shared/chakra.component';
import { FORM_STYLES } from './form.css';

/**
 * Sign in with the tenant key and username the farm was sent.
 * The one-click link carries them after `#`, so they never reach a server log.
 */
@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ChakraComponent],
  template: `
    <form class="card" (ngSubmit)="submit()">
      <h2>{{ t()('signIn') }}</h2>
      <app-chakra flow="access" [current]="3" [compact]="true" />
      <label class="f">{{ t()('tenantKey') }}
        <input name="key" [(ngModel)]="key" autocomplete="off" autocapitalize="off" spellcheck="false" class="mono" /></label>
      <label class="f">{{ t()('username') }}
        <input name="user" [(ngModel)]="user" autocomplete="username" autocapitalize="off" /></label>
      <div class="card err" *ngIf="error()" role="alert">{{ error() }}</div>
      <div class="wake" *ngIf="waking()">⏳ {{ t()('waking') }}</div>
      <button type="submit" [disabled]="busy() || !key.trim() || !user.trim()">{{ t()('signIn') }}</button>
      <p class="alt">{{ t()('noKey') }} <a routerLink="/register">{{ t()('register') }}</a></p>
    </form>
  `,
  styles: [FORM_STYLES],
})
export class LoginPage implements OnInit {
  private auth = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  t = inject(I18nService).t;
  key = '';
  user = '';
  busy = signal(false);
  waking = signal(false);
  error = signal('');

  ngOnInit(): void {
    const h = new URLSearchParams(location.hash.slice(1));
    if (h.get('k') && h.get('u')) {
      this.key = h.get('k')!;
      this.user = h.get('u')!;
      history.replaceState(null, '', location.pathname + location.search);   // the key leaves the address bar
      this.submit();
    }
  }

  async submit(): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    // A free server sleeps when idle; keep trying while it wakes instead of failing the farmer.
    for (let attempt = 0; attempt < 15; attempt++) {
      try {
        await this.auth.login(this.key, this.user);
        this.waking.set(false);
        this.busy.set(false);
        this.router.navigateByUrl(this.route.snapshot.queryParamMap.get('next') || '/count');
        return;
      } catch (e) {
        const status = e instanceof HttpErrorResponse ? e.status : 0;
        if ([0, 502, 503, 504].includes(status) && attempt < 14) {
          this.waking.set(true);
          await new Promise((r) => setTimeout(r, 4000));
          continue;
        }
        const detail = e instanceof HttpErrorResponse && typeof e.error?.detail === 'string' ? e.error.detail : '';
        this.error.set(status === 401 ? this.t()('loginFail') : detail || this.t()('netFail'));
        break;
      }
    }
    this.waking.set(false);
    this.busy.set(false);
  }
}
