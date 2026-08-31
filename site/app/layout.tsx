import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({ variable: '--font-geist-sans', subsets: ['latin'] });
const geistMono = Geist_Mono({ variable: '--font-geist-mono', subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Homelab Atlas | Docker architecture and stacks',
  description: 'Browse the live architecture and portable Docker Compose stacks behind a self-hosted homelab.',
  openGraph: { title: 'Homelab Atlas', description: 'Explore the live Docker homelab architecture and its stack model.', images: ['/og.png'] },
  twitter: { card: 'summary_large_image', title: 'Homelab Atlas', description: 'Explore the live Docker homelab architecture and its stack model.', images: ['/og.png'] },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body></html>;
}
