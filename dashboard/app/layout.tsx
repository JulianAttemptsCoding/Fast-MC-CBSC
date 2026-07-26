import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CBSC ZDC Event Observatory",
  description:
    "A localhost validation observatory for matched Geant4 and Fast-MC showers.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
