import { Injectable, computed, signal } from '@angular/core';

export interface LanguageInfo { code: string; native: string; english: string; speech: string; fallback: string | null; }
interface LanguageConfig { default: string; enabled: string[]; languages: LanguageInfo[]; }

const STORAGE_KEY = 'poultry360.lang';

/**
 * The reader's language. Every word on screen comes from assets/i18n/<code>.json;
 * the list of languages is assets/i18n/languages.json, so adding or hiding a
 * language is a config change. A missing word walks the fallback chain to English.
 */
@Injectable({ providedIn: 'root' })
export class I18nService {
  readonly available = signal<LanguageInfo[]>([]);
  readonly lang = signal<string>(stored() || 'en');
  readonly chosen = signal<boolean>(!!stored());
  readonly ready = signal(false);
  private dicts = signal<Record<string, Record<string, string>>>({});
  private config: LanguageConfig | null = null;

  /** Translate a key, with {name} placeholders filled from params. */
  readonly t = computed(() => {
    const code = this.lang(), dicts = this.dicts(), byCode = new Map(this.available().map((l) => [l.code, l]));
    return (key: string, params?: Record<string, string | number>): string => {
      let at: string | null | undefined = code;
      const seen = new Set<string>();
      let out: string | undefined;
      while (at && !seen.has(at)) {
        out = dicts[at]?.[key];
        if (out) break;
        seen.add(at);
        at = byCode.get(at)?.fallback ?? (at === 'en' ? null : 'en');
      }
      out = out ?? dicts['en']?.[key] ?? key;
      return params ? out.replace(/\{(\w+)\}/g, (_, p) => String(params[p] ?? '')) : out;
    };
  });

  readonly current = computed(() => this.available().find((l) => l.code === this.lang()));

  async init(): Promise<void> {
    try {
      this.config = await (await fetch('assets/i18n/languages.json')).json();
      const cfg = this.config!;
      this.available.set(cfg.languages.filter((l) => cfg.enabled.includes(l.code)));
      const fromLink = new URLSearchParams(location.hash.slice(1)).get('l') || new URLSearchParams(location.search).get('lang');
      const want = [fromLink, stored(), cfg.default].find((c) => c && cfg.enabled.includes(c)) || 'en';
      if (fromLink && cfg.enabled.includes(fromLink)) this.remember(fromLink);
      await this.use(want);
    } finally {
      this.ready.set(true);
    }
  }

  async set(code: string): Promise<void> {
    this.remember(code);
    await this.use(code);
  }

  private remember(code: string): void {
    this.chosen.set(true);
    try { localStorage.setItem(STORAGE_KEY, code); } catch { /* private mode */ }
  }

  private async use(code: string): Promise<void> {
    const chain: string[] = [];
    for (let at: string | null | undefined = code; at && !chain.includes(at); ) {
      chain.push(at);
      at = this.available().find((l) => l.code === at)?.fallback ?? (at === 'en' ? null : 'en');
    }
    if (!chain.includes('en')) chain.push('en');
    const loaded = { ...this.dicts() };
    await Promise.all(chain.filter((c) => !loaded[c]).map(async (c) => {
      try { loaded[c] = await (await fetch(`assets/i18n/${c}.json`)).json(); } catch { loaded[c] = {}; }
    }));
    this.dicts.set(loaded);
    this.lang.set(code);
    document.documentElement.lang = code;
  }
}

function stored(): string | null {
  try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
}
