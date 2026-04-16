import '@testing-library/jest-dom';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { mswServer } from './test/mswServer';

if (typeof window !== 'undefined') {
  window.scrollTo = () => {};
}

beforeAll(() => {
  mswServer.listen({ onUnhandledRequest: 'warn' });
});

afterEach(() => {
  mswServer.resetHandlers();
});

afterAll(() => {
  mswServer.close();
});
