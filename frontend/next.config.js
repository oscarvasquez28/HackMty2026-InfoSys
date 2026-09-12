/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // sql.js's UMD build probes for Node's fs/path/crypto even though the browser build never calls
  // them; without these fallbacks webpack fails to bundle it for the client (see lib/estate/sqlite.ts).
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = { ...config.resolve.fallback, fs: false, path: false, crypto: false };
    }
    return config;
  },
};

module.exports = nextConfig;
