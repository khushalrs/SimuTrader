/** @type {import('next').NextConfig} */

const apiOrigin =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const isDev = process.env.NODE_ENV !== "production";

// Content-Security-Policy is built dynamically so connect-src can reference
// the configured API origin at startup time.
const csp = [
  "default-src 'self'",
  // Next.js injects inline scripts for hydration — 'unsafe-inline' is
  // required until a nonce-based approach is adopted.
  // In dev, Fast Refresh / webpack HMR evaluate strings as JavaScript, so
  // 'unsafe-eval' is required there. It is never emitted in production.
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src 'self' ${apiOrigin}`,
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
].join("; ");

const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy",   value: csp },
          { key: "X-Frame-Options",           value: "DENY" },
          { key: "X-Content-Type-Options",    value: "nosniff" },
          { key: "Referrer-Policy",           value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy",        value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
