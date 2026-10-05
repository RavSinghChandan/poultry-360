import { Component, Input, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { I18nService } from '../core/i18n.service';
import { FLOW_ICONS } from '../core/strings-auth';

/**
 * A flow drawn as a chakra: each step is a node on the wheel, in order,
 * so a farmer sees where they are and what comes next without reading much.
 * `current` lights the step in progress; earlier steps show as done.
 */
@Component({
  selector: 'app-chakra',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="chakra" [class.compact]="compact">
      <svg viewBox="0 0 240 240" role="img" [attr.aria-label]="flowLabel()">
        <circle cx="120" cy="120" r="100" class="rim" />
        <circle cx="120" cy="120" r="84" class="rim thin" />
        <g class="spokes">
          <line *ngFor="let a of spokes" x1="120" y1="120"
                [attr.x2]="120 + 84 * cos(a)" [attr.y2]="120 + 84 * sin(a)" />
        </g>
        <circle cx="120" cy="120" r="34" class="hub" />
        <text x="120" y="117" class="hub-big">{{ shownIndex() }}</text>
        <text x="120" y="136" class="hub-small">{{ hubSmall() }}</text>
        <g *ngFor="let s of steps(); let i = index" class="node"
           [class.on]="i === current" [class.done]="current > i">
          <circle [attr.cx]="pos(i).x" [attr.cy]="pos(i).y" r="19" />
          <text [attr.x]="pos(i).x" [attr.y]="pos(i).y + 6" class="icon">{{ s.icon }}</text>
          <circle [attr.cx]="pos(i).x + 14" [attr.cy]="pos(i).y - 14" r="8" class="num" />
          <text [attr.x]="pos(i).x + 14" [attr.y]="pos(i).y - 10.5" class="num-t">{{ i + 1 }}</text>
        </g>
      </svg>
      <div class="now" *ngIf="compact && steps()[current] as s">
        <span class="n">{{ current + 1 }}</span><div><b>{{ s.label }}</b><small>{{ s.hint }}</small></div>
      </div>
      <ol *ngIf="!compact">
        <li *ngFor="let s of steps(); let i = index" [class.on]="i === current" [class.done]="current > i">
          <span class="n">{{ i + 1 }}</span>
          <div><b>{{ s.label }}</b><small>{{ s.hint }}</small></div>
        </li>
      </ol>
    </div>
  `,
  styles: [`
    .chakra{display:grid;gap:14px;align-items:center}
    @media(min-width:520px){.chakra:not(.compact){grid-template-columns:200px 1fr}}
    .compact{grid-template-columns:auto 1fr}
    .compact svg{width:110px}
    .now{display:flex;gap:10px;align-items:center}
    .now .n{flex:none;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:var(--accent);color:#fff;font-weight:800}
    .now b{display:block;font-size:17px} .now small{color:var(--muted);font-size:14px}
    svg{width:100%;max-width:240px;margin:0 auto;display:block}
    .rim{fill:none;stroke:var(--accent);stroke-width:3}
    .rim.thin{stroke-width:1;opacity:.45}
    .spokes{transform-origin:120px 120px;animation:turn 60s linear infinite}
    .spokes line{stroke:var(--accent);stroke-width:1;opacity:.3}
    .hub{fill:var(--accent-soft);stroke:var(--accent);stroke-width:2}
    .hub-big{font-size:24px;font-weight:800;text-anchor:middle;fill:var(--accent)}
    .hub-small{font-size:10px;text-anchor:middle;fill:var(--muted)}
    .node circle:first-child{fill:#fff;stroke:var(--line);stroke-width:2;transition:all .3s}
    .node.done circle:first-child{fill:var(--accent-soft);stroke:var(--accent)}
    .node.on circle:first-child{fill:var(--accent-soft);stroke:var(--accent);stroke-width:4}
    .node.on{animation:pulse 1.6s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
    .icon{font-size:17px;text-anchor:middle}
    .num{fill:var(--accent)} .num-t{font-size:10px;font-weight:800;fill:#fff;text-anchor:middle}
    ol{list-style:none;margin:0;padding:0;display:grid;gap:8px}
    li{display:flex;gap:10px;align-items:flex-start;padding:8px 10px;border-radius:10px;border:1px solid var(--line);background:#fff}
    li.on{border-color:var(--accent);background:var(--accent-soft)}
    li .n{flex:none;width:26px;height:26px;border-radius:50%;display:grid;place-items:center;background:var(--accent);color:#fff;font-weight:800;font-size:14px}
    li.done .n{opacity:.55}
    li b{display:block;font-size:16px} li small{color:var(--muted);font-size:14px}
    @keyframes turn{to{transform:rotate(360deg)}}
    @keyframes pulse{50%{opacity:.75}}
    @media (prefers-reduced-motion:reduce){.spokes,.node.on{animation:none}}
  `],
})
export class ChakraComponent {
  private i18n = inject(I18nService);
  private flow$ = signal('access');
  @Input() set flow(v: string) { this.flow$.set(v); }
  @Input() current = -1;
  @Input() compact = false;
  readonly spokes = Array.from({ length: 24 }, (_, i) => (i * 2 * Math.PI) / 24);

  steps = computed(() => {
    const t = this.i18n.t(), flow = this.flow$();
    return (FLOW_ICONS[flow] ?? []).map((icon, i) => ({ icon, label: t(`${flow}.${i + 1}`), hint: t(`${flow}.${i + 1}h`) }));
  });
  flowLabel = computed(() => this.steps().map((s, i) => `${i + 1}. ${s.label}`).join(', '));
  shownIndex() { return this.current >= 0 ? `${Math.min(this.current + 1, this.steps().length)}/${this.steps().length}` : `${this.steps().length}`; }
  hubSmall() { return this.i18n.t()('steps'); }

  pos(i: number) {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / this.steps().length;
    return { x: 120 + 100 * Math.cos(a), y: 120 + 100 * Math.sin(a) };
  }
  cos = Math.cos;
  sin = Math.sin;
}
