import { Component, input, signal } from '@angular/core';

/** A disclosure section.
 *
 * Content is projected and stays in the DOM when collapsed, so a section keeps its state
 * (a scrolled table, a typed filter) across open and close. That matters on a detail page
 * where sections are opened and closed repeatedly while comparing them. */
@Component({
  selector: 'app-accordion',
  template: `
    <section class="acc" [class.acc-open]="open()">
      <button class="acc-head" (click)="open.set(!open())"
              [attr.aria-expanded]="open()">
        <span class="acc-caret">{{ open() ? '▾' : '▸' }}</span>
        <span class="acc-title">{{ title() }}</span>
        @if (badge()) { <span class="acc-badge">{{ badge() }}</span> }
        @if (hint()) { <span class="acc-hint">{{ hint() }}</span> }
      </button>
      <div class="acc-body" [hidden]="!open()">
        <ng-content />
      </div>
    </section>
  `,
  styles: [`
    .acc {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      box-shadow: var(--shadow-sm);
      overflow: hidden;
    }
    .acc-head {
      display: flex; align-items: center; gap: .5rem; width: 100%;
      padding: .8125rem 1.125rem;
      border: none; background: none; font: inherit; text-align: left; cursor: pointer;
      transition: background .14s ease;
    }
    .acc-head:hover { background: var(--brand-050); }
    .acc-open .acc-head {
      background: linear-gradient(180deg, var(--brand-050), var(--surface));
      border-bottom: 1px solid var(--line);
    }
    .acc-caret { color: var(--brand-500); font-size: .75rem; width: 12px; }
    .acc-title { font-weight: 650; font-size: .875rem; color: var(--ink-900); }
    .acc-badge {
      font-size: .6875rem; font-weight: 700; background: var(--brand-100);
      color: var(--brand-700); padding: .0625rem .4375rem; border-radius: 999px;
    }
    .acc-hint { font-size: .75rem; color: var(--ink-500); margin-left: auto; }
    .acc-body { padding: 1.125rem; }
  `],
})
export class Accordion {
  readonly title = input.required<string>();
  readonly badge = input<string | number | null>(null);
  readonly hint = input<string>('');
  readonly open = signal(false);

  constructor() {
    queueMicrotask(() => { if (this.startOpen()) this.open.set(true); });
  }

  readonly startOpen = input<boolean>(false);
}
