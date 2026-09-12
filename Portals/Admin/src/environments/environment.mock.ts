/** No backend: every list is served from in-memory fixtures.
 *
 * Kept because UI work should not require Postgres, but it is no longer the default --
 * a portal that silently shows invented data is worse than one that shows an error.
 */
export const environment = {
  production: false,
  useMock: true,
  catalogBaseUrl: 'http://localhost:9001',
};
