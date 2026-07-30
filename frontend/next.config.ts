import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The frontend imports shared/contracts.json from the repo root, so Turbopack
  // must treat the repo — not frontend/ — as the project root.
  turbopack: {
    root: path.join(import.meta.dirname, ".."),
  },
  // The clinic runs this on its own LAN behind no CDN; the header adds nothing
  // but a version fingerprint for anyone scanning the network.
  poweredByHeader: false,
};

export default nextConfig;
