import "./styles/globals.css";
import { ReactNode } from "react";
import { LayoutShell } from "../components/LayoutShell";

export const metadata = {
  title: "Local Hoops Stats",
  description: "Local Basketball-Reference + Stathead-style clone",
};

/**
 * Root layout for the Next.js App Router.
 * Wraps all pages with the shared LayoutShell.
 */
export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <LayoutShell>{children}</LayoutShell>
      </body>
    </html>
  );
}