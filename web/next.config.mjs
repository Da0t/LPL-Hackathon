/** @type {import('next').NextConfig} */
const nextConfig = {
  // Intake may use several bounded model calls; keep the proxy open through the backend timeout.
  experimental: { proxyTimeout: 120000 },
  async rewrites() {
    return [{ source: '/api/:path*', destination: 'http://127.0.0.1:8000/:path*' }]
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
