'use client'
import Link from 'next/link'
import { Menu, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import React from 'react'
import { usePathname } from 'next/navigation'
import { BrandLogo } from '@/components/brand-logo'

export const HeroHeader = () => {
    const [menuState, setMenuState] = React.useState(false)
    const pathname = usePathname()
    // The advisor workspace has its own sidebar/chrome; hide the marketing header there.
    if (pathname?.startsWith('/dashboard')) return null
    return (
        <header>
            <nav
                data-state={menuState && 'active'}
                className="bg-background/50 fixed z-20 w-full border-b backdrop-blur-3xl">
                <div className="mx-auto max-w-6xl px-6 transition-all duration-300">
                    <div className="relative flex flex-wrap items-center justify-between gap-6 py-3 lg:gap-0 lg:py-4">
                        <div className="flex w-full items-center justify-between gap-12 lg:w-auto">
                            <Link href="/" aria-label="Coherent home" className="flex items-center gap-2">
                                <BrandLogo height={30} />
                            </Link>
                            <button
                                onClick={() => setMenuState(!menuState)}
                                aria-label={menuState ? 'Close Menu' : 'Open Menu'}
                                className="relative z-20 -m-2.5 -mr-4 block cursor-pointer p-2.5 lg:hidden">
                                <Menu className="in-data-[state=active]:rotate-180 in-data-[state=active]:scale-0 in-data-[state=active]:opacity-0 m-auto size-6 duration-200" />
                                <X className="in-data-[state=active]:rotate-0 in-data-[state=active]:scale-100 in-data-[state=active]:opacity-100 absolute inset-0 m-auto size-6 -rotate-180 scale-0 opacity-0 duration-200" />
                            </button>
                        </div>
                        <div className="bg-background in-data-[state=active]:block lg:in-data-[state=active]:flex mb-6 hidden w-full flex-wrap items-center justify-end gap-3 rounded-3xl border p-6 shadow-2xl md:flex-nowrap lg:m-0 lg:flex lg:w-fit lg:gap-3 lg:border-transparent lg:bg-transparent lg:p-0 lg:shadow-none">
                            <Button asChild size="sm" variant="ghost">
                                <Link href="/dashboard"><span>Advisor dashboard</span></Link>
                            </Button>
                            <Button asChild size="sm">
                                <Link href="/intake"><span>Start a request</span></Link>
                            </Button>
                        </div>
                    </div>
                </div>
            </nav>
        </header>
    )
}
