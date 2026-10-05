import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';
import { ChakraComponent } from '../shared/chakra.component';

/** The front door: how a farm gets in, and what each tool does, each as a chakra. */
@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterLink, ChakraComponent],
  template: `
    <section class="card">
      <h2>{{ t()('homeTitle') }}</h2>
      <p class="hint">{{ t()('homeLead') }}</p>
      <ng-container *ngIf="!auth.session(); else inside">
        <app-chakra flow="access" />
        <div class="two">
          <a class="btn" routerLink="/register">{{ t()('register') }}</a>
          <a class="btn ghost" routerLink="/login" [queryParams]="next()">{{ t()('signIn') }}</a>
        </div>
      </ng-container>
      <ng-template #inside>
        <p class="pill">{{ t()('farmOf') }} · {{ auth.session()!.tenantName }}</p>
      </ng-template>
    </section>

    <h3 class="how">{{ t()('howItWorks') }}</h3>
    <a *ngFor="let f of tools" class="card tool" [routerLink]="'/' + f.key">
      <app-chakra [flow]="f.key" [compact]="true" />
      <div>
        <b>{{ f.icon }} {{ t()(f.key + '.1') }} → {{ t()(f.key + '.' + f.last) }}</b>
        <ol><li *ngFor="let n of f.nums">{{ t()(f.key + '.' + n) }}</li></ol>
        <span class="go">{{ t()('start') }} →</span>
      </div>
    </a>
  `,
  styles: [`
    h2{margin:0 0 6px;font-size:22px}
    .two{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}
    .btn{display:block;text-align:center;padding:16px;border-radius:12px;background:var(--accent);color:#fff;font-weight:800;text-decoration:none}
    .btn.ghost{background:#fff;color:var(--accent);border:2px solid var(--accent)}
    .how{margin:22px 0 0;font-size:18px}
    .tool{display:grid;grid-template-columns:120px 1fr;gap:14px;align-items:center;text-decoration:none;color:var(--ink)}
    .tool ol{margin:6px 0;padding-left:20px;color:var(--muted);font-size:15px}
    .go{color:var(--accent);font-weight:800}
  `],
})
export class HomePage {
  auth = inject(AuthService);
  t = inject(I18nService).t;
  private route = inject(ActivatedRoute);
  next() { const n = this.route.snapshot.queryParamMap.get('next'); return n ? { next: n } : {}; }
  tools = [
    { key: 'count', icon: '📷', last: 4, nums: [1, 2, 3, 4] },
    { key: 'feed', icon: '🌾', last: 4, nums: [1, 2, 3, 4] },
    { key: 'health', icon: '🩺', last: 3, nums: [1, 2, 3] },
  ];
}
