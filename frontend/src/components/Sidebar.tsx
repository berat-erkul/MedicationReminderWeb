"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Özet" },
  { href: "/users", label: "Kişiler" },
  { href: "/medicines", label: "İlaçlar" },
  { href: "/schedules", label: "Program" },
  { href: "/reminders", label: "Hatırlatmalar" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="brand-block">
        <p className="brand-mark">Hatırlat</p>
        <p className="brand-sub">Aile ilaç paneli</p>
      </div>
      <nav className="nav">
        {links.map((link) => {
          const active = pathname === link.href;
          return (
            <Link key={link.href} href={link.href} className={active ? "nav-link active" : "nav-link"}>
              {link.label}
            </Link>
          );
        })}
      </nav>
      <p className="sidebar-foot">Home-server · local-first</p>
    </aside>
  );
}
