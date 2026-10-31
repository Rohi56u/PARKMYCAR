import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["cloudflare:workers", "node:sqlite"],
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
  typescript: {
    // Prevent deployment blocks on minor typing issues
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },
};

export default nextConfig;
