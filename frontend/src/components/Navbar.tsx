"use client";
import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Hexagon, Moon, Sun, Menu, X, FolderOpen, LogOut, User } from "lucide-react";
import { m, useScroll, useMotionValueEvent, AnimatePresence, useVelocity, Variants } from "framer-motion";
import { useTheme } from "./ThemeProvider";
import { useAuth } from "@/lib/auth-context";
import { getProjects } from "@/lib/projects-store";
import { AuthModal } from "@/components/AuthModal";
import { WelcomeBanner } from "@/components/WelcomeBanner";

export function Navbar() {
  const pathname = usePathname();
  const { scrollY } = useScroll();
  const scrollVelocity = useVelocity(scrollY);
  const [mounted, setMounted] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [welcomeVisible, setWelcomeVisible] = useState(false);
  const [welcomeName, setWelcomeName] = useState("");
  const [projectCount, setProjectCount] = useState(0);
  const userMenuRef = useRef<HTMLDivElement>(null);

  const isScrollingProgrammatically = useRef(false);
  const scrollTimeout = useRef<NodeJS.Timeout | null>(null);

  const [phase, setPhase] = useState<"top" | "pill" | "sphere">("sphere");
  const [isForcedPill, setIsForcedPill] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  const { setTheme, resolvedTheme } = useTheme();
  const currentTheme = mounted ? resolvedTheme : "dark";

  const { user, signIn, signOut } = useAuth();

  // FIX FE-006: Load project count on mount, user change, or route change.
  // Removed the `mounted` guard — it was delaying the first count load by
  // one extra render cycle, causing a 1-2s flash where the badge shows 0.
  useEffect(() => {
    const userId = user?.uid ?? null;

    const loadCount = async () => {
      const projects = await getProjects(userId);
      setProjectCount(projects.length);
    };
    loadCount();

    window.addEventListener("projects-updated", loadCount);
    return () => window.removeEventListener("projects-updated", loadCount);
  }, [user, pathname]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
    setIsMobile(window.innerWidth < 768);
    const timer = setTimeout(() => {
      const currentScroll = window.scrollY;
      if (currentScroll < 50) setPhase("top");
      else setPhase("pill");
    }, 400);
    return () => clearTimeout(timer);
  }, []);

  // FIX FE-008: Close mobile menu on route change (covers browser back/forward)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsMobileMenuOpen(false);
  }, [pathname]);

  // Ensure user dropdown and expansion safely close when shrinking to sphere
  useEffect(() => {
    if (phase === "sphere") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsExpanded(false);
      setUserMenuOpen(false);
    }
  }, [phase]);

  // Close user menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const toggleTheme = () => setTheme(resolvedTheme === "dark" ? "light" : "dark");

  const [activeTab, setActiveTab] = useState("home");

  const navLinks = [
    { name: "Home", href: "/", id: "home" },
    { name: "Features", href: "/#features", id: "features" },
    { name: "How It Works", href: "/#how-it-works", id: "how-it-works" },
    { name: "Projects", href: "/projects", id: "projects" },
  ];

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (pathname === "/projects") { setActiveTab("projects"); return; }
    if (pathname !== "/") { setActiveTab(""); return; }

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
    if (!mounted) return;
    if (isScrollingProgrammatically.current) {
      if (latest < 50) setPhase("top");
      else setPhase("pill");
      return;
    }
    const velocity = scrollVelocity.get();
    if (Math.abs(velocity) > 100) setIsForcedPill(false);
    if (latest < 50) { setPhase("top"); }
    else if (latest >= 50 && latest < 250) { setPhase("pill"); }
    else if (latest >= 250) {
      if (isForcedPill) { setPhase("pill"); }
      else if (velocity > 10) { setPhase("sphere"); }
      else if (velocity < -10) { setPhase("pill"); }
    }
  });

  const blur = isMobile ? "none" : "blur(20px)";
  const variants = {
    top: {
      width: "100%",
      maxWidth: "1000px",
      height: "64px",
      borderRadius: "999px",
      y: 20,
      backgroundColor: currentTheme === "dark" ? "rgba(255,255,255,0.02)" : "rgba(0,0,0,0.02)",
      border: "1px solid rgba(150,150,150,0.05)",
      padding: "0 24px",
      backdropFilter: blur,
      WebkitBackdropFilter: blur,
    },
    pill: {
      width: "100%",
      maxWidth: "780px",
      height: "60px",
      borderRadius: "999px",
      y: 20,
      backgroundColor: currentTheme === "dark" ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
      border: currentTheme === "dark" ? "1px solid rgba(255,255,255,0.1)" : "1px solid rgba(0,0,0,0.1)",
      padding: "0 24px",
      backdropFilter: blur,
      WebkitBackdropFilter: blur,
      boxShadow: "0 10px 40px rgba(0,0,0,0.1)"
    },
    sphere: {
      width: "60px",
      maxWidth: "60px",
      height: "60px",
      borderRadius: "999px",
      y: 20,
      backgroundColor: currentTheme === "dark" ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)",
      border: currentTheme === "dark" ? "1px solid rgba(255,255,255,0.3)" : "1px solid rgba(0,0,0,0.3)",
      padding: "0 10px",
      backdropFilter: blur,
      WebkitBackdropFilter: blur,
      boxShadow: "0 10px 40px rgba(0,0,0,0.2)"
    }
  };

  const leftVariants: Variants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, x: 0, transition: { delay: 0, type: "spring", stiffness: 300, damping: 24 } },
    exit: { opacity: 0, x: 20, scale: 0.9, transition: { duration: 0.2, ease: "easeOut" } }
  };

  const centerVariants: Variants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, transition: { delay: 0.15, type: "spring", stiffness: 300, damping: 24 } },
    exit: { opacity: 0, scale: 0.8, transition: { duration: 0.2, ease: "easeOut" } }
  };

  const rightVariants: Variants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, x: 0, transition: { delay: 0.3, type: "spring", stiffness: 300, damping: 24 } },
    exit: { opacity: 0, x: -20, scale: 0.9, transition: { duration: 0.2, ease: "easeOut" } }
  };

  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    setIsMobileMenuOpen(false);
    isScrollingProgrammatically.current = true;
    setPhase("pill");
    if (scrollTimeout.current) clearTimeout(scrollTimeout.current);
    scrollTimeout.current = setTimeout(() => { isScrollingProgrammatically.current = false; }, 1000);

    if (pathname === "/") {
      if (href === "/") { e.preventDefault(); window.scrollTo({ top: 0, behavior: "smooth" }); }
      else if (href.startsWith("/#")) {
        e.preventDefault();
        const id = href.split("#")[1];
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
      }
    }
  };

  const handleSignOut = async () => {
    setUserMenuOpen(false);
    await signOut();
  };

  const userInitial = user?.displayName?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || "U";
  const userFirstName = user?.displayName?.split(" ")[0] || user?.email?.split("@")[0] || "";

  return (
    <>
      <WelcomeBanner
        firstName={welcomeName}
        visible={welcomeVisible}
        onComplete={() => setWelcomeVisible(false)}
      />

      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onAuthSuccess={(u) => {
          setAuthModalOpen(false);
          const name = u.displayName?.split(" ")[0] || "there";
          setWelcomeName(name);
          setWelcomeVisible(true);
        }}
        onSkip={() => setAuthModalOpen(false)}
        signIn={signIn}
        signOut={signOut}
      />

      <div className="fixed top-0 left-0 w-full flex justify-center z-50 pointer-events-none px-4">
        <m.nav
          variants={variants}
          initial="sphere"
          animate={phase}
          transition={{ type: "spring", stiffness: 220, damping: 28, mass: 1 }}
          onAnimationComplete={(variant) => {
            if (variant === "top" || variant === "pill") setIsExpanded(true);
          }}
          onClick={() => {
            if (phase === "sphere") {
              if (window.innerWidth < 768) {
                // On mobile: tap the sphere to open the menu directly
                setIsMobileMenuOpen(true);
              } else {
                setIsForcedPill(true);
                setPhase("pill");
              }
            }
          }}
          className={`pointer-events-auto flex items-center justify-center mx-auto relative ${phase === "sphere" ? "cursor-pointer hover:scale-110 transition-transform active:scale-95 shadow-white/5" : ""
            } ${userMenuOpen ? "overflow-visible" : "overflow-hidden"}`}
        >
          {/* DECOUPLED STABLE LAYOUT: This prevents the components from jumping/squishing when the background shrinks */}
          <div className="absolute inset-0 w-full h-full flex justify-center items-center pointer-events-none">
            <div className="w-full h-full max-w-[1000px] flex items-center justify-between px-6 pointer-events-none relative">

              {/* Left Block (Logo & Brand) */}
              <div className="pointer-events-auto shrink-0 flex items-center z-10">
                <AnimatePresence>
                  {isExpanded && (
                    <m.div
                      key="left-logo"
                      variants={leftVariants}
                      initial="hidden"
                      animate="visible"
                      exit="exit"
                      className="flex items-center shrink-0"
                    >
                      <Link href="/" className="flex items-center gap-2.5 group transition-transform active:scale-95">
                        <div className="w-9 h-9 flex items-center justify-center">
                          <Hexagon className="text-[color:var(--text-primary)] w-7 h-7" />
                        </div>
                        <span className="font-bold text-xl tracking-tighter whitespace-nowrap overflow-hidden pr-2 text-[color:var(--text-primary)]">
                          ArchGuide.
                        </span>
                      </Link>
                    </m.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Center Block (Desktop Nav Links) */}
              <div className="pointer-events-auto shrink-0 flex items-center justify-center absolute left-1/2 -translate-x-1/2 z-0">
                <AnimatePresence>
                  {isExpanded && (
                    <m.div
                      key="nav-links"
                      variants={centerVariants}
                      initial="hidden"
                      animate="visible"
                      exit="exit"
                      className="hidden md:flex items-center gap-2 justify-center p-1"
                    >
                      {navLinks.map((link) => {
                        const isActive = activeTab === link.id;
                        return (
                          <Link
                            key={link.id}
                            href={link.href}
                            onClick={(e) => handleNavClick(e, link.href)}
                            className={`relative px-5 py-2 font-bold text-sm tracking-tight transition-all rounded-full z-10 flex items-center gap-2 whitespace-nowrap ${isActive ? "text-[color:var(--background)]" : "text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"}`}
                          >
                            {link.name}
                            {link.id === "projects" && projectCount > 0 && (
                              <span className={`text-[10px] font-black px-1.5 py-0.5 rounded-full min-w-[20px] text-center leading-none ${isActive ? "bg-[color:var(--background)] text-[color:var(--text-primary)]" : "bg-[color:var(--text-primary)] text-[color:var(--background)]"}`}>
                                {projectCount}
                              </span>
                            )}
                            {isActive && (
                              <m.div
                                layoutId="navbar-active-pill"
                                transition={{ type: "spring", stiffness: 400, damping: 35 }}
                                className="absolute inset-0 bg-[color:var(--text-primary)] rounded-full -z-10 shadow-sm"
                              />
                            )}
                          </Link>
                        );
                      })}
                    </m.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Right Block Container */}
              <div className="pointer-events-auto shrink-0 flex items-center z-10 gap-2.5">
                {/* Desktop Actions */}
                <AnimatePresence>
                  {isExpanded && (
                    <m.div
                      key="nav-actions"
                      variants={rightVariants}
                      initial="hidden"
                      animate="visible"
                      exit="exit"
                      className="hidden md:flex items-center gap-2.5"
                    >
                      {/* Theme Toggle */}
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleTheme(); }}
                        className="w-9 h-9 flex items-center justify-center rounded-full bg-[color:var(--text-primary)]/5 border border-[color:var(--border)] text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all active:scale-90"
                      >
                        {mounted ? (resolvedTheme === "dark" ? <Sun size={16} /> : <Moon size={16} />) : <div className="w-4 h-4" />}
                      </button>

                      {/* User Avatar, Sign In */}
                      {mounted ? (
                        user ? (
                          <div className="relative" ref={userMenuRef}>
                            <button
                              id="user-avatar-btn"
                              onClick={(e) => { e.stopPropagation(); setUserMenuOpen(!userMenuOpen); }}
                              className={`flex items-center gap-2 rounded-full border border-[color:var(--border)] bg-[color:var(--text-primary)]/5 hover:bg-[color:var(--text-primary)]/10 transition-all duration-300 ease-in-out active:scale-95 ${phase === "top" ? "px-4 py-2" : "p-1"}`}
                            >
                              <div className={`${phase === "top" ? "w-6 h-6 text-[10px]" : "w-7 h-7 text-[12px]"} rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] flex items-center justify-center font-black shrink-0 transition-all duration-300`}>
                                {userInitial}
                              </div>
                              {phase === "top" && (
                                <span className="text-sm font-bold text-[color:var(--text-primary)] max-w-[100px] truncate pr-1 transition-all duration-300">
                                  {userFirstName}
                                </span>
                              )}
                            </button>

                            <AnimatePresence>
                              {userMenuOpen && (
                                <m.div
                                  initial={{ opacity: 0, scale: 0.95, y: -8 }}
                                  animate={{ opacity: 1, scale: 1, y: 0 }}
                                  exit={{ opacity: 0, scale: 0.95, y: -8 }}
                                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                                  className="absolute right-0 top-[calc(100%+12px)] mt-0 w-48 rounded-2xl border border-[color:var(--border)] shadow-2xl overflow-hidden z-[9999]"
                                  style={{ background: "var(--surface)", backdropFilter: "blur(20px)" }}
                                >
                                  <div className="px-4 py-3 border-b border-[color:var(--border)]">
                                    <p className="text-sm font-black text-[color:var(--text-primary)] truncate">{user.displayName || "User"}</p>
                                    <p className="text-xs text-[color:var(--text-secondary)] truncate">{user.email}</p>
                                  </div>
                                  <Link
                                    href="/projects"
                                    onClick={() => setUserMenuOpen(false)}
                                    className="flex items-center gap-2.5 px-4 py-3 text-sm font-bold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)]/5 transition-all"
                                  >
                                    <FolderOpen size={14} /> My Projects
                                  </Link>
                                  <button
                                    id="sign-out-btn"
                                    onClick={handleSignOut}
                                    className="w-full flex items-center gap-2.5 px-4 py-3 text-sm font-bold text-red-500 hover:bg-red-500/10 transition-all"
                                  >
                                    <LogOut size={14} /> Sign Out
                                  </button>
                                </m.div>
                              )}
                            </AnimatePresence>
                          </div>
                        ) : (
                          <button
                            onClick={() => setAuthModalOpen(true)}
                            className={`flex items-center gap-2 rounded-full border border-[color:var(--border)] bg-[color:var(--text-primary)] text-[color:var(--background)] hover:opacity-90 transition-all duration-300 ease-in-out active:scale-95 ${phase === "top" ? "px-4 py-2" : "p-2"}`}
                          >
                            <User size={16} className={phase === "top" ? "w-4 h-4 transition-all duration-300" : "w-5 h-5 transition-all duration-300"} />
                            {phase === "top" && (
                              <span className="text-sm font-bold pr-1 transition-all duration-300">Sign In</span>
                            )}
                          </button>
                        )
                      ) : null}
                    </m.div>
                  )}
                </AnimatePresence>

                {/* Mobile Toggles */}
                <AnimatePresence>
                  {isExpanded && (
                    <m.div
                      key="mobile-toggle"
                      variants={rightVariants}
                      initial="hidden"
                      animate="visible"
                      exit="exit"
                      className="flex md:hidden items-center gap-2"
                    >
                      {mounted ? (
                        user ? (
                          <button
                            onClick={(e) => { e.stopPropagation(); setIsMobileMenuOpen(true); }}
                            className="w-8 h-8 flex items-center justify-center rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-black text-[11px] active:scale-95 transition-transform"
                          >
                            {userInitial}
                          </button>
                        ) : (
                          <button
                            onClick={(e) => { e.stopPropagation(); setAuthModalOpen(true); setIsMobileMenuOpen(false); }}
                            className="w-8 h-8 flex items-center justify-center rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] active:scale-95 transition-transform"
                          >
                            <User size={14} />
                          </button>
                        )
                      ) : (
                        <div className="w-8 h-8" />
                      )}

                      <button
                        onClick={(e) => { e.stopPropagation(); toggleTheme(); }}
                        className="w-8 h-8 flex items-center justify-center rounded-full bg-[color:var(--text-primary)]/5 border border-[color:var(--border)] text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all"
                      >
                        {mounted ? (resolvedTheme === "dark" ? <Sun size={14} /> : <Moon size={14} />) : <div className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setIsMobileMenuOpen(!isMobileMenuOpen); }}
                        className="w-9 h-9 flex items-center justify-center rounded-full text-[color:var(--text-primary)] active:scale-90 transition-transform"
                      >
                        {isMobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
                      </button>
                    </m.div>
                  )}
                </AnimatePresence>
              </div>

            </div>
          </div>

          {/* Center Block (Sphere Logo - only visible when not expanded) */}
          <AnimatePresence>
            {!isExpanded && (
              <m.div
                key="sphere-center-logo"
                initial={{ opacity: 0, scale: 0.5, rotate: -30 }}
                animate={{ opacity: 1, scale: 1, rotate: 0 }}
                exit={{ opacity: 0, scale: 0.5, rotate: 30 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
                className="absolute inset-0 flex items-center justify-center pointer-events-none"
              >
                <Hexagon size={26} className="text-[color:var(--text-primary)]" />
              </m.div>
            )}
          </AnimatePresence>
        </m.nav>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <m.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed inset-0 z-40 md:hidden bg-[color:var(--background)] pt-20 px-6 flex flex-col gap-4"
          >
            {/* Close button */}
            <button
              onClick={() => setIsMobileMenuOpen(false)}
              className="absolute top-5 right-5 w-10 h-10 flex items-center justify-center rounded-full bg-[color:var(--text-primary)]/8 border border-[color:var(--border)] text-[color:var(--text-primary)] active:scale-90 transition-transform"
            >
              <X size={20} />
            </button>

            <div className="flex flex-col gap-3">
              {navLinks.map((link, i) => {
                const isActive = activeTab === link.id;
                return (
                  <m.div
                    key={link.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.07 }}
                  >
                    <Link
                      href={link.href}
                      onClick={(e) => handleNavClick(e, link.href)}
                      className={`flex items-center justify-between w-full px-6 py-4 rounded-full text-lg font-bold transition-all border ${isActive
                        ? "bg-[color:var(--text-primary)] text-[color:var(--background)] border-transparent"
                        : "bg-[color:var(--text-primary)]/5 text-[color:var(--text-secondary)] border-[color:var(--border)]"
                        }`}
                    >
                      <span className="flex items-center gap-2">
                        {link.name}
                      </span>
                      {link.id === "projects" && projectCount > 0 && (
                        <span className={`text-xs font-black px-2.5 py-0.5 rounded-full ${isActive ? "bg-[color:var(--background)] text-[color:var(--text-primary)]" : "bg-[color:var(--text-primary)] text-[color:var(--background)]"}`}>
                          {projectCount}
                        </span>
                      )}
                    </Link>
                  </m.div>
                );
              })}
            </div>

            {/* Mobile: User actions */}
            <m.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.35 }}
              className="flex flex-col gap-2 mt-auto pb-8"
            >
              {user ? (
                <>
                  <div className="flex items-center gap-3 px-6 py-3 rounded-full border border-[color:var(--border)] bg-[color:var(--surface)]">
                    <div className="w-8 h-8 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] flex items-center justify-center text-sm font-black">
                      {userInitial}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-base font-bold truncate">{user.displayName}</p>
                      <p className="text-sm text-[color:var(--text-secondary)] truncate">{user.email}</p>
                    </div>
                  </div>
                  <button
                    onClick={handleSignOut}
                    className="flex items-center justify-center gap-2 w-full py-4 rounded-full border border-red-500/30 text-red-400 font-bold text-base"
                  >
                    <LogOut size={18} /> Sign Out
                  </button>
                </>
              ) : (
                <button
                  onClick={() => { setAuthModalOpen(true); setIsMobileMenuOpen(false); }}
                  className="flex items-center justify-center gap-2 w-full py-4 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold text-base"
                >
                  <User size={18} /> Sign In
                </button>
              )}
            </m.div>
          </m.div>
        )}
      </AnimatePresence>
    </>
  );
}