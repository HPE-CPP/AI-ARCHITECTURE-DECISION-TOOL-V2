import type { NextConfig } from "next";

const ContentSecurityPolicy = `
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com https://www.gstatic.com;
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob: https:;
font-src 'self' data:;
frame-src 'self' https://*.firebaseapp.com https://accounts.google.com;
connect-src 'self'
  http://localhost:8000
  ws://localhost:8000
  https://api.openai.com
  https://*.supabase.co
  https://*.googleapis.com
  https://*.firebaseapp.com
  https://identitytoolkit.googleapis.com;
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
`;

const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: ContentSecurityPolicy.replace(/\n/g, ""),
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=31536000; includeSubDomains; preload",
  },
  {
    key: "Cross-Origin-Opener-Policy",
    value: "same-origin-allow-popups",
  },
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "X-DNS-Prefetch-Control",
    value: "off",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    key: "X-Permitted-Cross-Domain-Policies",
    value: "none",
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
  compiler: {
    removeConsole: process.env.NODE_ENV === "production",
  },
  experimental: {
    optimizePackageImports: ["lucide-react", "framer-motion", "recharts"],
  },
};

export default nextConfig;
