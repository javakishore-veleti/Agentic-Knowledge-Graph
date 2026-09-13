export const environment = {
  production: true,
  useMock: false,
  // Same origin behind the gateway: no cross-origin call, no CORS config to maintain.
  catalogBaseUrl: '',
  // Acquisition runs in its own service: it triggers Airflow and outlives a request.
  dataMgmtBaseUrl: '/data-mgmt',
};
