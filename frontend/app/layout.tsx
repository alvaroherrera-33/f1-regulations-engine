import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import Navbar from '@/components/Navbar'

const inter = Inter({ subsets: ['latin'], display: 'swap' })

export const metadata: Metadata = {
    title: 'F1 Regulations Engine',
    description: 'Legal-grade RAG system for FIA Formula 1 regulations',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className={inter.className}>
            <body style={{ paddingTop: '60px' }}>
                <Navbar />
                {children}
            </body>
        </html>
    )
}
