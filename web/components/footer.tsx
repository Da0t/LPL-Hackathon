import Link from 'next/link'
import React from "react";
import { BrandLogo } from '@/components/brand-logo'

const links = [
    { title: 'Start a request', href: '/intake' },
    { title: 'Advisor dashboard', href: '/dashboard' },
    { title: 'Built on AWS', href: '/' },
]

export default function FooterSection() {
    return (
        <footer className="relative z-10 border-t border-border py-14">
            <div className="mx-auto max-w-5xl px-6">
                <Link href="/" aria-label="Coherent home" className="mx-auto flex w-fit items-center gap-2">
                    <BrandLogo height={30} />
                </Link>
                <div className="my-8 flex flex-wrap justify-center gap-6 text-sm">
                    {links.map((link, index) => (
                        <Link key={index} href={link.href}
                            className="text-muted-foreground hover:text-foreground block duration-150">
                            <span>{link.title}</span>
                        </Link>
                    ))}
                </div>
                <span className="text-muted-foreground block text-center text-sm font-mono">
                    AI intake &amp; triage on Amazon Bedrock · built for LPL Financial · synthetic data only
                </span>
            </div>
        </footer>
    )
}
