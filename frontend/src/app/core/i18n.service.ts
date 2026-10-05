import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AUTH_UI } from './strings-auth';

export interface LanguageInfo {
  code: string;
  native: string;
  english: string;
  default: boolean;
}

/** UI strings, per language. Server-sent text is translated server-side. */
const UI: Record<string, Record<string, string>> = {
  bn: {
    prompt: 'শেডের ছবি তুলুন',
    takePhoto: '📷 ছবি তুলুন',
    recordVideo: '🎥 ভিডিও করুন',
    videoFindsMore: 'ছবির চেয়ে ভিডিওতে বেশি পাখি ধরা পড়ে',
    counting: 'গোনা হচ্ছে…',
    watching: 'ভিডিও দেখা হচ্ছে… একটু সময় লাগবে',
    birdsFound: 'পাখি পাওয়া গেছে',
    enterCorrect: 'সঠিক সংখ্যা লিখুন',
    recordNumber: 'এই সংখ্যা রেকর্ড করুন',
    clear: 'নিশ্চিত',
    uncertain: 'অনিশ্চিত',
    framesChecked: 'ফ্রেম দেখা হয়েছে',
    bestFrame: 'এক ফ্রেমে সর্বোচ্চ',
    readFail: 'ফাইলটি পড়া যায়নি',
    countFail: 'গোনা যায়নি',
    saveFail: 'রেকর্ড করা যায়নি',
    language: 'ভাষা',
  },
  hi: {
    prompt: 'शेड की फ़ोटो लें',
    takePhoto: '📷 फ़ोटो लें',
    recordVideo: '🎥 वीडियो लें',
    videoFindsMore: 'वीडियो में ज़्यादा पक्षी मिलते हैं',
    counting: 'गिन रहे हैं…',
    watching: 'वीडियो देख रहे हैं… कुछ समय लगेगा',
    birdsFound: 'पक्षी मिले',
    enterCorrect: 'सही संख्या भरें',
    recordNumber: 'दर्ज करें',
    clear: 'पक्का',
    uncertain: 'हो सकता है',
    framesChecked: 'फ़्रेम देखे',
    bestFrame: 'एक फ़्रेम में सबसे ज़्यादा',
    readFail: 'फ़ाइल पढ़ी नहीं गई',
    countFail: 'गिनती नहीं हो सकी',
    saveFail: 'दर्ज नहीं हुआ',
    language: 'भाषा',
  },
  bho: {
    prompt: 'शेड के फोटो लीं',
    takePhoto: '📷 फोटो लीं',
    recordVideo: '🎥 वीडियो लीं',
    videoFindsMore: 'वीडियो में जादा पंछी मिलेला',
    counting: 'गिनत बानी…',
    watching: 'वीडियो देखत बानी… कुछ समय लागी',
    birdsFound: 'पंछी मिलल',
    enterCorrect: 'सही संख्या भरीं',
    recordNumber: 'दर्ज करीं',
    clear: 'पक्का',
    uncertain: 'हो सकेला',
    framesChecked: 'फ्रेम देखल',
    bestFrame: 'एक फ्रेम में सबसे जादा',
    readFail: 'फाइल पढ़ल ना गइल',
    countFail: 'गिनती ना हो सकल',
    saveFail: 'दर्ज ना भइल',
    language: 'भाषा',
  },
  mai: {
    prompt: 'शेडक फोटो लिअ',
    takePhoto: '📷 फोटो लिअ',
    recordVideo: '🎥 वीडियो लिअ',
    videoFindsMore: 'वीडियोमे बेसी पक्षी भेटैत अछि',
    counting: 'गनि रहल छी…',
    watching: 'वीडियो देखि रहल छी… किछु समय लागत',
    birdsFound: 'पक्षी भेटल',
    enterCorrect: 'सही संख्या भरू',
    recordNumber: 'दर्ज करू',
    clear: 'पक्का',
    uncertain: "भ' सकैत अछि",
    framesChecked: 'फ्रेम देखल',
    bestFrame: 'एक फ्रेममे सबसँ बेसी',
    readFail: 'फाइल पढ़ल नहि गेल',
    countFail: 'गनती नहि भेल',
    saveFail: 'दर्ज नहि भेल',
    language: 'भाषा',
  },
  en: {
    prompt: 'Photograph the shed',
    takePhoto: '📷 Take a photo',
    recordVideo: '🎥 Record a video',
    videoFindsMore: 'a video finds more birds than a photo',
    counting: 'Counting…',
    watching: 'Watching the video… this takes a moment',
    birdsFound: 'birds found',
    enterCorrect: 'Enter the correct number',
    recordNumber: 'Record this number',
    clear: 'clear',
    uncertain: 'uncertain',
    framesChecked: 'frames checked',
    bestFrame: 'best single frame',
    readFail: 'Could not read that file',
    countFail: 'Counting failed',
    saveFail: 'Could not record',
    language: 'Language',
  },
};

for (const [code, strings] of Object.entries(AUTH_UI)) UI[code] = { ...strings, ...UI[code] };

/** Which language to try when one has no string. Mirrors the backend. */
const FALLBACK: Record<string, string> = { bho: 'hi', mai: 'hi', bn: 'en', hi: 'en' };

const STORAGE_KEY = 'poultry360.lang';

/**
 * The reader's language.
 *
 * Stored in localStorage so a farmer picks once. Sent as `lang` on every API
 * call, so the server resolves its own text and the client never has to
 * translate anything it received.
 */
@Injectable({ providedIn: 'root' })
export class I18nService {
  private http = inject(HttpClient);
  private base = location.port === '4200' ? 'http://localhost:8000' : '';

  readonly available = signal<LanguageInfo[]>([]);
  readonly lang = signal<string>(this.initial());

  /** Translate a UI key, walking the fallback chain. */
  readonly t = computed(() => {
    const code = this.lang();
    return (key: string): string => {
      let at: string | undefined = code;
      const seen = new Set<string>();
      while (at && !seen.has(at)) {
        const hit = UI[at]?.[key];
        if (hit) return hit;
        seen.add(at);
        at = FALLBACK[at];
      }
      return UI['en'][key] ?? key;
    };
  });

  constructor() {
    this.http
      .get<{ languages: LanguageInfo[]; default: string }>(`${this.base}/api/languages`)
      .subscribe({
        next: (r) => {
          this.available.set(r.languages);
          if (!localStorage.getItem(STORAGE_KEY)) this.lang.set(r.default);
        },
        error: () => {},
      });
  }

  set(code: string): void {
    this.lang.set(code);
    try {
      localStorage.setItem(STORAGE_KEY, code);
    } catch {
      /* private browsing; the choice simply will not persist */
    }
  }

  private initial(): string {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return saved;
    } catch {
      /* ignore */
    }
    return 'bn';
  }
}
