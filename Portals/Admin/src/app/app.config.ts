import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideRouter } from '@angular/router';

import { CATALOG_BASE_URL, CatalogApi, HttpCatalogApi, MockCatalogApi } from './core/catalog-api';
import { environment } from '../environments/environment';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withFetch()),
    { provide: CATALOG_BASE_URL, useValue: environment.catalogBaseUrl },
    // One token, two implementations. Components never name either: switching to the
    // real service is a flag, not a code change.
    { provide: CatalogApi, useClass: environment.useMock ? MockCatalogApi : HttpCatalogApi },
  ],
};
