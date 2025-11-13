"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links: { href: string; label: string }[] = [
  { href: "/players", label: "Players" },
  { href: "/teams", label: "Teams" },
  { href: "/seasons", label: "Seasons" },
  { href: "/games", label: "Games" },
  { href: "/tools", label: "Tools Home" },
  { href: "/tools/leaderboards", label: "Leaderboards" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/tools") {
    return pathname === "/tools";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Top navigation bar used in [`components/LayoutShell.tsx`](components/LayoutShell.tsx:1).
 */
export function NavBar() {
  const pathname = usePathname() || "/";

  return (
    <nav className="nav-bar">
      {links.map((link) => {
        const active = isActive(pathname, link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={
              "nav-link" + (active ? " nav-link-active" : "")
            }
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}