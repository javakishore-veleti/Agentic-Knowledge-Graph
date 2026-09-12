import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

/** Administration shell. One left-nav section today; more will follow. */
@Component({
  selector: 'page-administration',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="admin">
      <aside class="sidenav">
        <div class="sidenav-head">
          <h2>Administration</h2>
          <p class="muted tiny">Setup and operational tasks</p>
        </div>
        <nav>
          <a class="sidenav-item" routerLink="initial-data" routerLinkActive="is-active">
            <span class="sidenav-label">Initial Data</span>
            <span class="sidenav-hint">Populate a blank database</span>
          </a>
          <span class="sidenav-item is-planned">
            <span class="sidenav-label">Tenancy</span>
            <span class="sidenav-hint">Tenants and PHI mode</span>
            <span class="planned-tag">planned</span>
          </span>
          <span class="sidenav-item is-planned">
            <span class="sidenav-label">Access</span>
            <span class="sidenav-hint">Roles and permissions</span>
            <span class="planned-tag">planned</span>
          </span>
        </nav>
      </aside>
      <section class="admin-body"><router-outlet /></section>
    </div>
  `,
  styleUrl: './administration.scss',
})
export class Administration {}
