import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

/** A feature as the backend describes it. The menu is built from this. */
export interface FeatureInfo {
  key: string;
  /** Resolved for the requested language by the server. */
  name: string;
  summary: string;
  name_en: string;
  name_hi: string;
  summary_en: string;
  summary_hi: string;
  version: string;
  status: 'live' | 'beta' | 'planned';
  icon: string;
  sources: string[];
  healthy: boolean;
  problems: string[];
  base_path: string;
}

export interface Ration {
  day: number; birds: number; phase: string;
  phase_name_en: string; phase_name_hi: string;
  crude_protein_pct: number; energy_kcal_per_kg: number;
  lysine_pct: number; methionine_pct: number; calcium_pct: number;
  feed_per_bird_g: number; feed_total_kg: number;
  target_weight_g: number | null;
  note_en: string; note_hi: string;
  source: string[]; dataset_version: string;
}

/**
 * The only place the API base URL is decided.
 *
 * On `ng serve` (port 4200) the backend is a separate process on 8000. The
 * static copy on Vercel opens instantly and calls the API on Render, which can
 * take ~30 s to wake on the free tier. When FastAPI serves this bundle itself,
 * the API is same-origin.
 */
export const API_BASE =
  location.port === '4200' ? 'http://localhost:8000'
  : location.hostname.endsWith('.vercel.app') ? 'https://poultry-360.onrender.com'
  : '';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = API_BASE;

  features(lang?: string): Observable<{ features: FeatureInfo[] }> {
    const q = lang ? `?lang=${encodeURIComponent(lang)}` : '';
    return this.http.get<{ features: FeatureInfo[] }>(`${this.base}/api/features${q}`);
  }

  /** Generic feature call, so a new feature needs no new method here. */
  post<T>(featureKey: string, path: string, body: unknown): Observable<T> {
    return this.http.post<T>(`${this.base}/api/${featureKey}/${path}`, body);
  }

  get<T>(featureKey: string, path: string): Observable<T> {
    return this.http.get<T>(`${this.base}/api/${featureKey}/${path}`);
  }
}
