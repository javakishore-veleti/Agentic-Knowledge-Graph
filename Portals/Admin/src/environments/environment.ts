/** Local development.
 *
 * `useMock` keeps the portal usable when the middleware stack is not running. Set it to
 * false (or use environment.api.ts) to hit the real DataCatalog service on :8001. */
export const environment = {
  production: false,
  useMock: true,
  catalogBaseUrl: 'http://localhost:8001',
};
