"use client";

import type { ReactNode } from "react";
import { NavBar } from "./NavBar";

export interface LayoutShellProps {
  title?: string;
  children?: ReactNode;
}

/**
 * Simple layout wrapper used by App Router pages.
 * Rendered inside [`app/layout.tsx`](app/layout.tsx:1).
 */
export function LayoutShell({ title, children }: LayoutShellProps) {
  return (
    <div className="app-root">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="app-brand">
            <a href="/">Local Hoops Stats</a>
          </div>
          <NavBar />
        </div>
      </header>
      <main className="app-main">
        {title && <h1 className="page-title">{title}</h1>}
        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}