import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts"],
    exclude: ["node_modules", ".next"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
      // 'server-only' es un guard de Next que rompe en Node test runner.
      // Lo mapeamos a un módulo vacío para que los imports de archivos
      // server-side (T2.1.B bridge) puedan testearse en vitest.
      "server-only": path.resolve(__dirname, "lib/__mocks__/server-only.ts"),
    },
  },
});
