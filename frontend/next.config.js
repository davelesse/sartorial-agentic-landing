/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,

  // API proxying vers le backend FastAPI
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000/api/v1'}/:path*`,
      },
    ];
  },

  // Images — only explicitly allowed hostnames
  images: {
    remotePatterns: [],
  },
};

module.exports = nextConfig;
