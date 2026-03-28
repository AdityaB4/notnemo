import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "fische",
  description: "Find the internet's most niche gems.",
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
