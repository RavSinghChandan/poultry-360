import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { API_BASE } from '../core/auth.service';
import { FORM_STYLES } from './form.css';
import { I18nService } from '../core/i18n.service';

interface Reg {
  id: string; farm: string; owner: string; email: string; phone: string; district: string;
  status: 'pending' | 'approved' | 'rejected' | 'revoked'; tenant: string | null; username: string | null; tenant_key: string | null;
}
interface Ops {
  uptime_s: number; requests: number; server_error_rate: number;
  routes: { route: string; count: number; client_errors: number; server_errors: number; p50_ms: number | null; p95_ms: number | null }[];
  farms_today: Record<string, number>;
  model: { calls: number; failed: number; fallback_rate: number; p50_ms: number | null; p95_ms: number | null; prompt_tokens: number; completion_tokens: number };
}
const KEY = 'poultry360.admin';

/** The owner's page: approve farms and send them their tenant key + username. */
@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <form class="card" *ngIf="!unlocked(); else open" (ngSubmit)="unlock()">
      <h2>Farm access · Owner</h2>
      <label class="f">Admin key<input name="key" type="password" [(ngModel)]="adminKey" autocomplete="off" /></label>
      <div class="card err" *ngIf="error()" role="alert">{{ error() }}</div>
      <button type="submit" [disabled]="!adminKey.trim()">Open</button>
    </form>

    <ng-template #open>
      <section class="card issued" *ngIf="issued() as k" role="status">
        <b>Access issued · send this to {{ k.owner }}</b>
        <dl>
          <dt>Farm</dt><dd>{{ k.farm }}</dd>
          <dt>Tenant key</dt><dd class="mono">{{ k.tenant_key }}</dd>
          <dt>Username</dt><dd class="mono">{{ k.username }}</dd>
          <dt>Sign-in link</dt><dd class="mono"><a [href]="link(k)" target="_blank" rel="noopener">{{ link(k) }}</a></dd>
        </dl>
        <div class="acts">
          <button type="button" (click)="copy(link(k))">{{ copied() ? 'Copied ✓' : 'Copy sign-in link' }}</button>
          <button type="button" class="ghost" (click)="copy(message(k))">Copy message</button>
          <a *ngIf="k.phone" class="ghost btnlike" [href]="whatsapp(k)" target="_blank" rel="noopener">WhatsApp it</a>
          <a *ngIf="k.email" class="ghost btnlike" [href]="mailto(k)">Email it</a>
          <button type="button" class="ghost" (click)="issued.set(null)">Done</button>
        </div>
      </section>

      <section class="card ops" *ngIf="ops() as o">
        <div class="opshead"><b>Service health</b><button type="button" class="ghost mini" (click)="loadOps()">Refresh</button></div>
        <div class="tiles">
          <div><span>{{ o.requests }}</span>API calls</div>
          <div [class.bad]="o.server_error_rate > 0.01"><span>{{ (o.server_error_rate * 100) | number:'1.0-1' }}%</span>server errors</div>
          <div><span>{{ o.model.calls }}</span>AI calls</div>
          <div [class.bad]="o.model.fallback_rate > 0.1"><span>{{ (o.model.fallback_rate * 100) | number:'1.0-0' }}%</span>AI fell back</div>
          <div><span>{{ o.model.p95_ms ?? '–' }}</span>AI p95 ms</div>
          <div><span>{{ o.model.prompt_tokens + o.model.completion_tokens }}</span>tokens</div>
        </div>
        <p class="hint">Since the server started {{ uptime(o.uptime_s) }} ago.</p>
        <table *ngIf="o.routes.length">
          <tr><th>Route</th><th>Calls</th><th>Errors</th><th>p50</th><th>p95</th></tr>
          <tr *ngFor="let r of o.routes.slice(0, 8)"><td class="mono">{{ r.route }}</td><td>{{ r.count }}</td>
            <td>{{ r.server_errors }}</td><td>{{ r.p50_ms ?? '–' }}</td><td>{{ r.p95_ms ?? '–' }}</td></tr>
        </table>
        <p class="hint" *ngIf="farmsToday(o).length">Farms active today: <span *ngFor="let f of farmsToday(o); let last = last">{{ f[0] }} ({{ f[1] }}){{ last ? '' : ', ' }}</span></p>
      </section>

      <section class="card">
        <label class="f">Language for sign-in links
          <select [(ngModel)]="linkLang" name="ll" class="sel">
            <option *ngFor="let l of i18n.available()" [value]="l.code">{{ l.native }} · {{ l.english }}</option>
          </select>
        </label>
        <p class="hint">A farm opening its link sees the app in this language. It can change it any time.</p>
      </section>

      <h3>Waiting for approval <span class="pill">{{ pending().length }}</span></h3>
      <p class="hint" *ngIf="!pending().length">No new requests.</p>
      <article class="card" *ngFor="let r of pending()">
        <b>{{ r.farm }}</b>
        <div class="hint">{{ r.owner }}{{ r.phone ? ' · ' + r.phone : '' }}{{ r.email ? ' · ' + r.email : '' }}{{ r.district ? ' · ' + r.district : '' }}</div>
        <label class="f">Username <span class="hint">(optional)</span>
          <input [(ngModel)]="usernames[r.id]" [name]="'u' + r.id" autocapitalize="off" /></label>
        <div class="acts">
          <button type="button" (click)="approve(r)" [disabled]="busy()">Approve</button>
          <button type="button" class="ghost" (click)="reject(r)" [disabled]="busy()">Reject</button>
        </div>
      </article>

      <h3>Give access directly</h3>
      <form class="card" (ngSubmit)="issueDirect()">
        <label class="f">Farm name<input name="df" [(ngModel)]="direct.farm" /></label>
        <label class="f">Owner name<input name="do" [(ngModel)]="direct.owner" /></label>
        <label class="f">Phone <span class="hint">(optional)</span><input name="dp" [(ngModel)]="direct.phone" /></label>
        <label class="f">Username <span class="hint">(optional)</span><input name="du" [(ngModel)]="direct.username" autocapitalize="off" /></label>
        <button type="submit" [disabled]="busy() || direct.farm.trim().length < 2 || !direct.owner.trim()">Issue tenant key</button>
      </form>

      <h3>Farms with access <span class="pill">{{ approved().length }}</span></h3>
      <article class="card" *ngFor="let r of approved()">
        <b>{{ r.farm }}</b>
        <div class="hint">{{ r.username }} · <span class="mono">{{ r.tenant_key }}</span></div>
        <div class="acts">
          <button type="button" class="ghost" (click)="copy(link(r))">Copy link</button>
          <button type="button" class="ghost" (click)="copy(message(r))">Copy message</button>
          <button type="button" class="ghost" (click)="reject(r)">Turn off</button>
        </div>
      </article>
      <div class="card err" *ngIf="error()" role="alert">{{ error() }}</div>
    </ng-template>
  `,
  styles: [FORM_STYLES + `
    h3{margin:22px 0 0;font-size:18px}
    .issued{border:2px solid var(--accent)}
    dl{display:grid;grid-template-columns:110px 1fr;gap:6px 10px;margin:10px 0}
    dt{color:var(--muted);font-size:15px} dd{margin:0;font-weight:700;font-size:15px}
    .acts{display:flex;flex-wrap:wrap;gap:8px}
    .acts button,.btnlike{width:auto;margin-top:10px;padding:10px 14px;font-size:15px;border-radius:10px}
    .ghost{background:#fff;color:var(--accent);border:2px solid var(--accent)}
    .btnlike{text-decoration:none;font-weight:800;display:inline-block}
    .opshead{display:flex;justify-content:space-between;align-items:center}
    .mini{width:auto!important;margin:0!important;padding:6px 12px!important;font-size:14px!important}
    .tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0 4px}
    .tiles div{background:var(--bg,#f6f7f4);border-radius:10px;padding:10px 8px;font-size:13px;color:var(--muted);text-align:center}
    .tiles span{display:block;font-size:20px;font-weight:800;color:inherit}
    .tiles div:not(.bad) span{color:#1c1c1c} .tiles .bad span{color:#b42318}
    table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}
    th,td{text-align:left;padding:5px 4px;border-bottom:1px solid var(--line)} td.mono{word-break:break-all}
    .sel{width:100%;min-height:52px;font-size:17px;padding:10px;border:2px solid var(--line);border-radius:12px;background:#fff;margin-top:6px}
  `],
})
export class AdminPage {
  private http = inject(HttpClient);
  i18n = inject(I18nService);
  linkLang = 'en';
  adminKey = read();
  unlocked = signal(false);
  rows = signal<Reg[]>([]);
  ops = signal<Ops | null>(null);
  busy = signal(false);
  error = signal('');
  issued = signal<Reg | null>(null);
  copied = signal(false);
  usernames: Record<string, string> = {};
  direct = { farm: '', owner: '', phone: '', username: '' };
  pending = computed(() => this.rows().filter((r) => r.status === 'pending'));
  approved = computed(() => this.rows().filter((r) => r.status === 'approved'));

  constructor() { if (this.adminKey) this.unlock(); }

  private headers() { return new HttpHeaders({ 'x-admin-key': this.adminKey.trim() }); }

  async unlock(): Promise<void> {
    this.error.set('');
    try {
      this.rows.set(await firstValueFrom(this.http.get<Reg[]>(`${API_BASE}/api/admin/registrations`, { headers: this.headers() })));
      this.unlocked.set(true);
      this.loadOps();
      try { sessionStorage.setItem(KEY, this.adminKey.trim()); } catch { /* private mode */ }
    } catch (e) {
      this.unlocked.set(false);
      this.error.set(e instanceof HttpErrorResponse && e.status === 401 ? 'That admin key is not right.' : 'Could not reach the server. It may be waking up, try again.');
    }
  }

  async loadOps(): Promise<void> {
    try { this.ops.set(await firstValueFrom(this.http.get<Ops>(`${API_BASE}/api/admin/ops`, { headers: this.headers() }))); }
    catch { /* the panel is optional; approvals still work */ }
  }
  farmsToday(o: Ops) { return Object.entries(o.farms_today); }
  uptime(s: number) { return s < 3600 ? `${Math.max(1, Math.round(s / 60))} min` : `${Math.round(s / 3600)} h`; }

  approve(r: Reg) { return this.act(`/api/admin/registrations/${r.id}/approve`, { username: (this.usernames[r.id] || '').trim() }); }
  reject(r: Reg) { return this.act(`/api/admin/registrations/${r.id}/reject`, {}, false); }
  async issueDirect() {
    await this.act('/api/admin/issue', { ...this.direct });
    this.direct = { farm: '', owner: '', phone: '', username: '' };
  }

  private async act(path: string, body: object, showIssued = true): Promise<void> {
    this.busy.set(true);
    this.error.set('');
    try {
      const res = await firstValueFrom(this.http.post<Reg>(`${API_BASE}${path}`, body, { headers: this.headers() }));
      if (showIssued && res.tenant_key) { this.issued.set(res); this.copied.set(false); }
      await this.unlock();
    } catch (e) {
      const d = e instanceof HttpErrorResponse ? e.error?.detail : null;
      this.error.set(typeof d === 'string' ? d : 'That did not work. Please try again.');
    } finally {
      this.busy.set(false);
    }
  }

  /** One-click sign-in: the key sits after #, so it is never sent to a server. */
  link(k: Reg) { return `${location.origin}/login#k=${encodeURIComponent(k.tenant_key || '')}&u=${encodeURIComponent(k.username || '')}&l=${this.linkLang}`; }
  message(k: Reg) {
    return `Hi ${k.owner}, your farm ${k.farm} is ready on Poultry 360.\n\nOne-click sign-in: ${this.link(k)}\n\nOr sign in at ${location.origin}/login with\nTenant key: ${k.tenant_key}\nUsername: ${k.username}`;
  }
  whatsapp(k: Reg) {
    const digits = k.phone.replace(/\D/g, '');
    return `https://wa.me/${digits.length === 10 ? '91' + digits : digits}?text=${encodeURIComponent(this.message(k))}`;
  }
  mailto(k: Reg) { return `mailto:${k.email}?subject=${encodeURIComponent('Your Poultry 360 access')}&body=${encodeURIComponent(this.message(k))}`; }
  async copy(text: string) { try { await navigator.clipboard.writeText(text); this.copied.set(true); } catch { /* clipboard blocked */ } }
}

function read(): string { try { return sessionStorage.getItem(KEY) || ''; } catch { return ''; } }
