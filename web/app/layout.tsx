import React from "react"
import type {Metadata} from 'next'
import {Geist, Geist_Mono} from 'next/font/google'
import {Analytics} from '@vercel/analytics/next'
import './globals.css'
import {HeroHeader} from "@/components/header";

const geistSans = Geist({subsets: ["latin"], variable: "--font-geist-sans"});
const geistMono = Geist_Mono({subsets: ["latin"], variable: "--font-geist-mono"});

export const metadata: Metadata = {
    title: 'Coherent — Your words. The right advisor.',
    description: 'Coherent helps wealth-management clients describe what they need in plain language and routes a clear, confirmed request to the right advisor. AI intake and triage powered by Amazon Bedrock, built for LPL Financial.',
    generator: 'Coherent',
    icons: {
        icon: [
            {
                url: '/icon-light-32x32.png',
                media: '(prefers-color-scheme: light)',
            },
            {
                url: '/icon-dark-32x32.png',
                media: '(prefers-color-scheme: dark)',
            },
            {
                url: '/icon.svg',
                type: 'image/svg+xml',
            },
        ],
        apple: '/apple-icon.png',
    },
}

export default function RootLayout({
                                       children,
                                   }: Readonly<{
    children: React.ReactNode
}>) {
    return (
        <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
        <body className="font-sans antialiased">
        <HeroHeader/>
        {children}
        <Analytics/>
        </body>
        </html>
    )
}
