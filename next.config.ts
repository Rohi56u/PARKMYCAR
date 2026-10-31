import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["cloudflare:workers", "node:sqlite"],
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
