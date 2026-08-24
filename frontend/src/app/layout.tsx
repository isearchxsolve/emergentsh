import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'NeonBuild - Build Apps with AI',
  description: 'An agentic AI platform that builds full-stack applications from natural language descriptions',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased dark:bg-dark-900 dark:text-white">
        {children}
      </body>
    </html>
  );
}
