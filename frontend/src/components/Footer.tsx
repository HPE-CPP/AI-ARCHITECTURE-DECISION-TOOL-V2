"use client";

import React from "react";
import Link from "next/link";
import { Hexagon } from "lucide-react"; // Changed to lucide-react if using standard package
import { motion } from "framer-motion";

export function Footer() {
  const footerLinks = [
    {
      title: "Navigation",
      links: [
        { name: "Download", href: "#" },
        { name: "Product", href: "#" },
        { name: "Docs", href: "#" },
        { name: "Changelog", href: "#" },
        { name: "Press", href: "#" },
        { name: "Releases", href: "#" },
      ],
    },
    {
      title: "Resources",
      links: [
        { name: "Blog", href: "#" },
        { name: "Pricing", href: "#" },
        { name: "Use Cases", href: "#" },
      ],
    },
  ];

  return (
    <footer className="w-full min-h-screen bg-[color:var(--background)] border-t border-[color:var(--border)] overflow-hidden flex flex-col justify-between">
      {/* Top Content Section */}
      <div className="w-full px-8 md:px-16 pt-32">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-20 mb-32">
          <div className="lg:col-span-1">
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-8">
              Experience <br />
              <span className="opacity-40 font-black">liftoff.</span>
            </h2>
          </div>

          <div className="lg:col-span-2 grid grid-cols-2 gap-10">
            {footerLinks.map((column, i) => (
              <div key={i}>
                <h4 className="text-xs font-bold uppercase tracking-[0.2em] text-[color:var(--text-secondary)] mb-6">
                  {column.title}
                </h4>
                <ul className="space-y-4">
                  {column.links.map((link, j) => (
                    <li key={j}>
                      <Link
                        href={link.href}
                        className="text-sm font-medium text-[color:var(--text-primary)] hover:opacity-60 transition-opacity"
                      >
                        {link.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Hero Text Section */}
        <div className="relative mb-20">
          <motion.h1
            initial={{ y: 100, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
            className="text-[15vw] md:text-[16vw] font-bold tracking-[-0.05em] leading-none text-[color:var(--text-primary)] pointer-events-none select-none"
          >
            ARCHGUIDE.
          </motion.h1>
        </div>
      </div>

      {/* Bottom Legal/Social Bar */}
      <div className="w-full px-8 md:px-16 pb-12 pt-12 border-t border-[color:var(--border)] flex flex-col md:flex-row justify-between items-center gap-8">
        <div className="flex items-center gap-3">
          <Hexagon size={24} />
          <span className="font-bold text-lg tracking-tighter">ARCHGUIDE.</span>
        </div>

        <div className="flex items-center gap-8 text-xs font-medium text-[color:var(--text-secondary)]">
          <Link href="#">About ArchGuide</Link>
          <Link href="#">ArchGuide Products</Link>
          <Link href="#">Privacy</Link>
          <Link href="#">Terms</Link>
        </div>
      </div>
    </footer>
  );
}