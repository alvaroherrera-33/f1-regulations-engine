import type { Metadata } from 'next'
import './globals.css'
import Navbar from '@/components/Navbar'

export const metadata: Metadata = {
    title: 'F1 Regulations Engine',
    description: 'Legal-grade RAG system for FIA Formula 1 regulations',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body style={{ paddingTop: '60px' }}>
                <Navbar />
                {children}
            </body>
        </html>
    )
}
