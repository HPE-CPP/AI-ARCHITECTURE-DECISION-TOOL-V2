import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ['192.168.29.145'],
  serverExternalPackages: ['jspdf', 'jspdf-autotable', 'fflate'],
  turbopack: {},
};

export default nextConfig;
