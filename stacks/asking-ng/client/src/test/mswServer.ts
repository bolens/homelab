import { setupServer } from 'msw/node';

/** Extend with `server.use(...)` in individual tests. */
export const mswServer = setupServer();
