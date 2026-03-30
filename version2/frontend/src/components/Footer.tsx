"use client";

import React from "react";
import Link from "next/link";
import { Hexagon } from "lucide-react";
import { motion, Variants } from "framer-motion";

export function Footer() {
  const footerLinks = [
    {
      title: "Navigation",
      links: [
        { name: "Home", href: "/" },
        { name: "Features", href: "/#features" },
        { name: "How It Works", href: "/#how-it-works" },
      ],
    },
    {
      title: "Product",
      links: [
        { name: "Projects", href: "/projects" },
        { name: "Begin Analysis", href: "/projects" },
      ],
    },
  ];

  const brandName = "ARCHGUIDE.";

  // Animation variants
  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.04,
      },
    },
  };

  const letterVariants: Variants = {
    hidden: { y: "110%", opacity: 0 },
    visible: {
      y: 0,
      opacity: 1,
      transition: {
        duration: 0.8,
        ease: [0.16, 1, 0.3, 1],
      },
    },
  };

  return (
    <footer className="w-full bg-[color:var(--background)] border-t border-[color:var(--border)] overflow-hidden flex flex-col justify-between">
      {/* Top Content Section */}
      <div className="w-full px-6 md:px-16 pt-24 md:pt-32">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-12 md:gap-20 mb-20 md:mb-32">
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

        {/* Hero Text Section - Optimized for Single Line & No Wrap */}
        <div className="relative w-full overflow-hidden pb-4">
          <motion.h1
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: false, amount: 0.1 }}
            // Changed text size to 13vw and forced flex-nowrap to keep it on one line
            className="text-[13vw] font-bold tracking-[-0.01em] leading-[0.85] text-[color:var(--text-primary)] pointer-events-none select-none flex flex-nowrap whitespace-nowrap"
          >
            {brandName.split("").map((char, index) => (
              <span
                key={index}
                className="inline-block overflow-hidden"
              >
                <motion.span
                  variants={letterVariants}
                  style={{ display: "inline-block" }}
                >
                  {char}
                </motion.span>
              </span>
            ))}
          </motion.h1>
        </div>
      </div>

      {/* Bottom Legal/Social Bar */}
      <div className="w-full px-6 md:px-16 pb-12 pt-12 border-t border-[color:var(--border)] flex flex-col md:flex-row justify-between items-center gap-8">
        <div className="flex items-center gap-3">
          <Hexagon size={24} />
          <span className="font-bold text-lg tracking-tighter">ARCHGUIDE.</span>
        </div>

        <div className="flex flex-wrap justify-center items-center gap-x-8 gap-y-4 text-xs font-medium text-[color:var(--text-secondary)]">
          <Link href="/" className="hover:text-[color:var(--text-primary)] transition-colors">About ArchGuide</Link>
          <Link href="/projects" className="hover:text-[color:var(--text-primary)] transition-colors">Projects</Link>
        </div>
      </div>
    </footer>
  );
}