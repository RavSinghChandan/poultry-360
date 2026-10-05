import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, firstValueFrom, throwError } from 'rxjs';

export interface Session { token: string; name: string; tenant: string; tenantName: string; }
const KEY = 'poultry360.session';
export const API_BASE = location.port === '4200' ? 'http://localhost:8000' : '';

/** The signed-in farm. The token is signed by the server and lasts 7 days. */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  readonly session = signal<Session | null>(read());
  /** Unknown until the server answers; treated as required so nothing leaks. */
  readonly required = signal<boolean | null>(null);

  async status(): Promise<boolean> {
    if (this.required() !== null) return this.required()!;
    try {
      const r = await firstValueFrom(this.http.get<{ required: boolean }>(`${API_BASE}/api/auth/status`));
      this.required.set(r.required);
    } catch { return true; }
    return this.required()!;
  }

  async login(tenantKey: string, username: string): Promise<Session> {
    const r = await firstValueFrom(this.http.post<{ token: string; name: string; tenant: string; tenant_name: string }>(
      `${API_BASE}/api/auth/login`, { tenant_key: tenantKey.trim(), username: username.trim() }));
    const s = { token: r.token, name: r.name, tenant: r.tenant, tenantName: r.tenant_name };
    this.session.set(s);
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private mode */ }
    return s;
  }

  register(body: { farm: string; owner: string; phone: string; email: string; district: string }) {
    return firstValueFrom(this.http.post<{ id: string; status: string }>(`${API_BASE}/api/auth/register`, body));
  }

  logout(): void {
    this.session.set(null);
    try { localStorage.removeItem(KEY); } catch { /* ignore */ }
  }
}

function read(): Session | null {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch { return null; }
}

/** Adds the farm's token to API calls; a refused token sends the farmer back to sign in. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const s = auth.session();
  const isApi = req.url.startsWith(`${API_BASE}/api/`) && !req.url.includes('/api/admin/');
  const out = s && isApi ? req.clone({ setHeaders: { Authorization: `Bearer ${s.token}` } }) : req;
  return next(out).pipe(catchError((e: HttpErrorResponse) => {
    if (e.status === 401 && isApi && !req.url.includes('/api/auth/')) {
      auth.logout();
      router.navigate(['/login'], { queryParams: { next: router.url } });
    }
    return throwError(() => e);
  }));
};

export const signedIn: CanActivateFn = async (_r, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);           // before the await: injection only works synchronously
  if (auth.session() || !(await auth.status())) return true;
  return router.createUrlTree(['/welcome'], { queryParams: { next: state.url } });
};
