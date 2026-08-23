/** @type {import('next').NextConfig} */
const BACKEND_BASE = (process.env.BACKEND_API_URL || 'http://localhost:8000').replace(/\/api\/?$/, '');

const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_BASE}/api/:path*`,
      },
      {
        // EM-6: the workspace preview iframe loads /preview/{jobId}/ — proxy it
        // to the backend's StaticFiles mount so live previews actually render.
        source: '/preview/:path*',
        destination: `${BACKEND_BASE}/preview/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;