"use client";
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Hexagon, Moon, Sun, Menu, X } from "lucide-react";
import { motion, useScroll, useMotionValueEvent, AnimatePresence, useVelocity } from "framer-motion";
import { useTheme } from "./ThemeProvider";

export function Navbar() {
  const pathname = usePathname();
  const { scrollY } = useScroll();
  const scrollVelocity = useVelocity(scrollY);
  const [mounted, setMounted] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const { setTheme, resolvedTheme } = useTheme();
  const currentTheme = mounted ? resolvedTheme : "dark";

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  };

  const [activeTab, setActiveTab] = useState("home");
  const [phase, setPhase] = useState<"top" | "pill" | "sphere">("top");
  const [isForcedPill, setIsForcedPill] = useState(false);

  const navLinks = [
    { name: "Home", href: "/", id: "home" },
    { name: "Features", href: "/#features", id: "features" },
    { name: "How It Works", href: "/#how-it-works", id: "how-it-works" },
    { name: "Analyze", href: "/analyze", id: "analyze" },
  ];

  useEffect(() => {
    if (pathname === "/analyze") {
      setActiveTab("analyze");
      return;
    }
    if (pathname !== "/") {
      setActiveTab("");
      return;
    }

    const handleScroll = () => {
      const sections = ["home", "features", "how-it-works"];
      const scrollPos = window.scrollY + 150;

      for (const section of sections) {
        const element = document.getElementById(section);
        if (element) {
          const top = element.offsetTop;
          const height = element.offsetHeight;
          if (scrollPos >= top && scrollPos < top + height) {
            setActiveTab(section);
            break;
          }
        }
      }
    };

    handleScroll();
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [pathname]);

  useMotionValueEvent(scrollY, "change", (latest) => {
    const velocity = scrollVelocity.get();
    if (Math.abs(velocity) > 100) setIsForcedPill(false);

    if (latest < 50) {
      setPhase("top");
    } else if (latest >= 50 && latest < 250) {
      setPhase("pill");
    } else if (latest >= 250) {
      if (isForcedPill) {
        setPhase("pill");
      } else if (velocity > 10) {
        setPhase("sphere");
      } else if (velocity < -10) {
        setPhase("pill");
      }
    }
  });

  const variants = {
    top: {
      width: "100%",
      maxWidth: "800px",
      borderRadius: "99px",
      y: 20,
      backgroundColor: currentTheme === "dark" ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.02)",
      border: "1px solid rgba(150,150,150,0.05)",
      padding: "12px 24px",
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
    },
    pill: {
      width: "100%",
      maxWidth: "600px",
      borderRadius: "99px",
      y: 20,
      backgroundColor: currentTheme === "dark" ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
      border: currentTheme === "dark" ? "1px solid rgba(255,255,255,0.1)" : "1px solid rgba(0,0,0,0.1)",
      padding: "10px 24px",
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
      boxShadow: "0 10px 40px rgba(0,0,0,0.1)"
    },
    sphere: {
      width: "56px",
      maxWidth: "56px",
      borderRadius: "99px",
      y: 20,
      backgroundColor: currentTheme === "dark" ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)",
      border: currentTheme === "dark" ? "1px solid rgba(255,255,255,0.3)" : "1px solid rgba(0,0,0,0.3)",
      padding: "10px",
      backdropFilter: "blur(20px)",
      WebkitBackdropFilter: "blur(20px)",
      boxShadow: "0 10px 40px rgba(0,0,0,0.2)"
    }
  };

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    setIsMobileMenuOpen(false); // Close mobile menu on click
    if (pathname === "/") {
      if (href === "/") {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else if (href.startsWith("/#")) {
        e.preventDefault();
        const id = href.split("#")[1];
        const element = document.getElementById(id);
        if (element) {
          element.scrollIntoView({ behavior: "smooth" });
        }
      }
    } else if (pathname === "/analyze" && href === "/analyze") {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <>
      <div className="fixed top-0 left-0 w-full flex justify-center z-50 pointer-events-none px-4">
        <motion.nav
          variants={variants}
          initial="top"
          animate={phase}
          transition={{ type: "spring", stiffness: 220, damping: 28, mass: 1 }}
          onClick={() => {
            if (phase === "sphere") {
              setIsForcedPill(true);
              setPhase("pill");
            }
          }}
          className={`pointer-events-auto flex items-center justify-between overflow-hidden mx-auto shadow-2xl ${phase === "sphere" ? "cursor-pointer hover:scale-110 transition-transform active:scale-95 shadow-white/5" : ""}`}
        >
          {/* Logo Container */}
          <Link href="/" className="flex items-center gap-2 group shrink-0 relative z-10 transition-transform active:scale-95">
            <div className="w-8 h-8 flex items-center justify-center">
              <Hexagon className="text-[color:var(--text-primary)] w-6 h-6" />
            </div>
            <AnimatePresence>
              {phase !== "sphere" && (
                <motion.span
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: "auto" }}
                  exit={{ opacity: 0, width: 0 }}
                  className="font-bold text-lg tracking-tighter whitespace-nowrap overflow-hidden pr-2 text-[color:var(--text-primary)]"
                >
                  ArchGuide.
                </motion.span>
              )}
            </AnimatePresence>
          </Link>

          {/* Desktop Navigation Items (Hidden on Mobile) */}
          <AnimatePresence>
            {phase !== "sphere" && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="hidden md:flex items-center gap-1 justify-center shrink-0 relative z-0 p-1"
              >
                {navLinks.map((link) => {
                  const isActive = activeTab === link.id;
                  return (
                    <Link
                      key={link.id}
                      href={link.href}
                      onClick={(e) => handleNavClick(e, link.href)}
                      className={`relative px-4 py-1.5 font-bold text-xs tracking-tight transition-all rounded-full z-10 ${isActive ? "text-[color:var(--background)]" : "text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                        }`}
                    >
                      {link.name}
                      {isActive && (
                        <motion.div
                          layoutId="navbar-active-pill"
                          transition={{ type: "spring", stiffness: 400, damping: 35 }}
                          className="absolute inset-0 bg-[color:var(--text-primary)] rounded-full -z-10 shadow-sm"
                        />
                      )}
                    </Link>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Actions & Mobile Toggle */}
          <AnimatePresence>
            {phase !== "sphere" && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-2 shrink-0 relative z-10"
              >
                <button
                  onClick={(e) => { e.stopPropagation(); toggleTheme(); }}
                  className="hidden md:flex w-8 h-8 items-center justify-center rounded-full bg-[color:var(--text-primary)]/5 border border-[color:var(--border)] text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all active:scale-90"
                >
                  {mounted ? (resolvedTheme === "dark" ? <Moon size={14} /> : <Sun size={14} />) : <div className="w-3.5 h-3.5" />}
                </button>

                {/* Mobile Menu Button */}
                <button
                  onClick={(e) => { e.stopPropagation(); setIsMobileMenuOpen(!isMobileMenuOpen); }}
                  className="md:hidden w-8 h-8 flex items-center justify-center rounded-full text-[color:var(--text-primary)] active:scale-90 transition-transform"
                >
                  {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Sphere Logo */}
          {phase === "sphere" && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="absolute inset-0 flex items-center justify-center">
              <Hexagon size={24} className="text-[color:var(--text-primary)]" />
            </motion.div>
          )}
        </motion.nav>
      </div>

      {/* Mobile Menu Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed inset-0 z-40 md:hidden bg-[color:var(--background)] pt-24 px-6 flex flex-col gap-4"
          >
            <div className="flex flex-col gap-3">
              {navLinks.map((link, i) => {
                const isActive = activeTab === link.id;
                return (
                  <motion.div
                    key={link.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                  >
                    <Link
                      href={link.href}
                      onClick={(e) => handleNavClick(e, link.href)}
                      className={`block w-full px-6 py-4 rounded-full text-lg font-bold transition-all border ${isActive
                          ? "bg-[color:var(--text-primary)] text-[color:var(--background)] border-transparent"
                          : "bg-[color:var(--text-primary)]/5 text-[color:var(--text-secondary)] border-[color:var(--border)]"
                        }`}
                    >
                      {link.name}
                    </Link>
                  </motion.div>
                );
              })}
            </div>

            {/* Theme Toggle in Mobile Menu */}
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
              onClick={toggleTheme}
              className="mt-4 flex items-center justify-center gap-2 w-full py-4 rounded-full border border-[color:var(--border)] text-[color:var(--text-primary)] font-bold"
            >
              {resolvedTheme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              Switch to {resolvedTheme === "dark" ? "Light" : "Dark"} Mode
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}