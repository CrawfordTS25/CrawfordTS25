import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['server/**/*.test.ts', 'brand/**/*.test.ts'],
    // The live hub is timing-sensitive; give sockets room without being slow.
    testTimeout: 15_000,
    hookTimeout: 15_000,
  },
});
