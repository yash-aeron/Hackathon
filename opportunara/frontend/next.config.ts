import type { NextConfig } from "next";

/**
 * Scoutly frontend configuration.
 *
 * `cacheComponents`/`partialPrefetching` are intentionally left off: every
 * screen is a client component that talks to the Scoutly API at runtime, so
 * there is no server-rendered data to cache. The Turbopack CSS rule is what
 * wires Tailwind v4 into the pipeline for this template.
 */
const nextConfig: NextConfig = {
  reactStrictMode: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
