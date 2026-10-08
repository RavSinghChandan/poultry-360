import { Injectable, inject, signal } from '@angular/core';
import { I18nService } from './i18n.service';

/**
 * Reads the screen aloud in the chosen language, for farmers who do not read
 * comfortably. Uses the phone's own voices; nothing is sent anywhere.
 */
@Injectable({ providedIn: 'root' })
export class SpeechService {
  private i18n = inject(I18nService);
  readonly supported = typeof window !== 'undefined' && 'speechSynthesis' in window;
  readonly speaking = signal(false);

  /** Read the visible text of an element, skipping anything marked data-noread. */
  readElement(el: Element | null): void {
    if (!el) return;
    const clone = el.cloneNode(true) as HTMLElement;
    clone.querySelectorAll('[data-noread], svg, script, style, input, select').forEach((n) => n.remove());
    this.say((clone.innerText || clone.textContent || '').replace(/\s+/g, ' ').trim());
  }

  say(text: string): void {
    if (!this.supported || !text) return;
    speechSynthesis.cancel();
    const locale = this.i18n.current()?.speech || 'en-IN';
    const u = new SpeechSynthesisUtterance(text.slice(0, 1500));
    u.lang = locale;
    u.rate = 0.92;
    const voice = speechSynthesis.getVoices().find((v) => v.lang.replace('_', '-').toLowerCase() === locale.toLowerCase())
      ?? speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith(locale.slice(0, 2).toLowerCase()));
    if (voice) u.voice = voice;
    u.onend = u.onerror = () => this.speaking.set(false);
    this.speaking.set(true);
    speechSynthesis.speak(u);
  }

  stop(): void {
    if (this.supported) speechSynthesis.cancel();
    this.speaking.set(false);
  }
}
