import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import "./board.css";
export const metadata: Metadata = { title: "Shields", manifest: "/manifest.webmanifest", robots: { index: false, follow: false } };
export const viewport: Viewport = { themeColor: "#0b0f14", width: "device-width", initialScale: 1 };
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const nonce = (await headers()).get("x-nonce") ?? undefined; // set by middleware.ts; no inline script or style needs 'unsafe-inline'
  return (
    <ClerkProvider dynamic>
      <html lang="en"><body>
        {children}
        <script src="/sw-register.js" nonce={nonce} defer />
      </body></html>
    </ClerkProvider>
  );
}
