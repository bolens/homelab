import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Models import `../connections` at load time; URI must resolve without real Postgres for unit tests.
    env: {
      POSTGRES_USER: 'vitest',
      POSTGRES_PASSWORD: 'vitest',
      POSTGRES_DB: 'vitest',
      POSTGRES_HOST: '127.0.0.1',
      POSTGRES_PORT: '5432',
    },
    environment: 'node',
    globals: true,
    include: ['**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      include: ['src/**/*.ts'],
      exclude: ['**/*.test.ts', 'src/types/**', 'src/models/**'],
    },
  },
});
