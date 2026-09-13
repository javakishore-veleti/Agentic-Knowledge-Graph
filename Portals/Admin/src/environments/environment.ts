/** Local development against the real DataCatalog service.
 *
 * Requires the stack: `npm run local:stack:up` starts Postgres, applies the migrations
 * and runs the API on :8001. On a blank database every list is empty until
 * Administration -> Initial Data has been run, which is the intended first-run
 * experience rather than a fault.
 *
 * To work on the UI without any backend, use `ng serve --configuration mock`, which
 * swaps in environment.mock.ts.
 */
export const environment = {
  production: false,
  useMock: false,
  catalogBaseUrl: 'http://localhost:9001',
  // Acquisition runs in its own service: it triggers Airflow and outlives a request.
  dataMgmtBaseUrl: 'http://localhost:9002',
};
