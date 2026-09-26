import { createReadStream, existsSync, statSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

const repoFixtures = resolve(import.meta.dirname, "../fixtures");

// Serves the repo-root /fixtures directory at /fixtures during dev, so the app can run on
// VITE_USE_FIXTURES=true without a backend. Dev server only; not part of the build.
function serveFixtures(): Plugin {
  return {
    name: "serve-fixtures",
    configureServer(server) {
      server.middlewares.use("/fixtures", (req, res, next) => {
        const file = resolve(repoFixtures, "." + decodeURIComponent((req.url ?? "/").split("?")[0]));
        const rel = relative(repoFixtures, file);
        const inside = rel !== "" && !rel.startsWith("..") && !isAbsolute(rel);
        if (!inside || !existsSync(file) || !statSync(file).isFile()) {
          return next();
        }
        if (file.endsWith(".json")) res.setHeader("Content-Type", "application/json");
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), serveFixtures()],
  server: {
    port: 5173,
    // Backend runs on :8000 (see `make dev`); the app calls /api/* on its own origin.
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
