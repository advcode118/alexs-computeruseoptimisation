import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingIncludes: {
    "/": ["./public/index.html"],
  },
};

export default nextConfig;
