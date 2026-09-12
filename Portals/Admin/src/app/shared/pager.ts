import { Component, input, output } from '@angular/core';

/** Cursor pagination control.
 *
 * The API returns an opaque next_cursor rather than offsets, because offsets shift under
 * concurrent inserts and silently skip rows. That means "previous" cannot be computed --
 * it is a stack of the cursors already visited, which this keeps for the caller. */
@Component({
  selector: 'app-pager',
  template: `
    <div class="pager">
      <span class="muted tiny">
        {{ shown() }} of {{ total() }}{{ total() === 1 ? ' item' : ' items' }}
      </span>
      <div class="spacer"></div>
      <button class="btn btn-secondary" [disabled]="!canPrev()" (click)="prev.emit()">
        Previous
      </button>
      <button class="btn btn-secondary" [disabled]="!nextCursor()" (click)="next.emit()">
        Next
      </button>
    </div>
  `,
  styles: [`
    .pager {
      display: flex; align-items: center; gap: .625rem;
      padding: .75rem 1.375rem;
      border-top: 1px solid var(--line);
      background: var(--surface-sunken);
      border-radius: 0 0 var(--radius) var(--radius);
    }
    .spacer { flex: 1; }
  `],
})
export class Pager {
  readonly shown = input.required<number>();
  readonly total = input.required<number>();
  readonly nextCursor = input<string | null>(null);
  readonly canPrev = input<boolean>(false);
  readonly next = output<void>();
  readonly prev = output<void>();
}
