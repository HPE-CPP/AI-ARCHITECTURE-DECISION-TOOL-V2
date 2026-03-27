"use client";
import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Hexagon, Moon, Sun, Menu, X, FolderOpen, LogOut, User } from "lucide-react";
import { motion, useScroll, useMotionValueEvent, AnimatePresence, useVelocity, Variants } from "framer-motion";
import { useTheme } from "./ThemeProvider";
import { useAuth } from "@/lib/auth-context";
import { getProjects } from "@/lib/projects-store";
import { AuthModal } from "@/components/AuthModal";
import { WelcomeBanner } from "@/components/WelcomeBanner";

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
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

  const { setTheme, resolvedTheme } = useTheme();
  const currentTheme = mounted ? resolvedTheme : "dark";

  const { user, signIn, signOut } = useAuth();

  // Load project count for badge
  useEffect(() => {
    if (!mounted) return;
    const userId = user?.uid ?? null;

    const loadCount = () => {
      getProjects(userId).then(projects => setProjectCount(projects.length));
    };
    loadCount();

    window.addEventListener("projects-updated", loadCount);
    return () => window.removeEventListener("projects-updated", loadCount);
  }, [mounted, user, pathname]);

  useEffect(() => {
    setMounted(true);
    const timer = setTimeout(() => {
      const currentScroll = window.scrollY;
      if (currentScroll < 50) setPhase("top");
      else setPhase("pill");
    }, 400);
    return () => clearTimeout(timer);
  }, []);

  // Expanded-collapse ref so we can cancel on fast re-expand
  const collapseTimer = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (phase === "sphere") {
      // Give nav items time to fade out before the spring contraction fires
      if (collapseTimer.current) clearTimeout(collapseTimer.current);
      collapseTimer.current = setTimeout(() => setIsExpanded(false), 220);
    } else {
      // Cancel any pending collapse if user scrolls back up quickly
      if (collapseTimer.current) clearTimeout(collapseTimer.current);
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
    if (pathname === "/analyze") { setActiveTab("analyze"); return; }
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

  const variants = {
    top: {
      width: "100%",
      maxWidth: "860px",
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
      maxWidth: "680px",
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

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 20 },
    visible: (customDelay: number) => ({
      opacity: 1,
      y: 0,
      transition: { delay: customDelay, type: "spring", stiffness: 300, damping: 24 }
    }),
    // Slow, graceful fade — gives the sphere spring animation time to catch up
    exit: { opacity: 0, y: 0, filter: "blur(4px)", transition: { duration: 0.22, ease: "easeInOut" } }
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
    } else if (pathname === "/analyze" && href === "/analyze") {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const handleSignOut = async () => {
    setUserMenuOpen(false);
    await signOut();
  };

  // Get user display info
  const userInitial = user?.displayName?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || "U";
  const userFirstName = user?.displayName?.split(" ")[0] || user?.email?.split("@")[0] || "";

  return (
    <>
      {/* Expose WelcomeBanner and AuthModal when signed out and clicking Sign In */}
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
        <motion.nav
          variants={variants}
          initial="sphere"
          animate={phase}
          transition={phase === "sphere"
            ? { type: "spring", stiffness: 220, damping: 28, mass: 1, delay: 0.18 }
            : { type: "spring", stiffness: 220, damping: 28, mass: 1 }}
          onAnimationComplete={(variant) => {
            if (variant === "top" || variant === "pill") setIsExpanded(true);
          }}
          onClick={() => {
            if (phase === "sphere") { setIsForcedPill(true); setPhase("pill"); }
          }}
          className={`pointer-events-auto flex items-center justify-between mx-auto shadow-2xl ${phase === "sphere" ? "cursor-pointer hover:scale-110 transition-transform active:scale-95 shadow-white/5" : ""}`}
        >
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group shrink-0 relative z-10 transition-transform active:scale-95">
            <div className={`w-8 h-8 flex items-center justify-center transition-opacity duration-300 ${isExpanded ? "opacity-100" : "opacity-0"}`}>
              <Hexagon className="text-[color:var(--text-primary)] w-6 h-6" />
            </div>
            <AnimatePresence>
              {isExpanded && (
                <motion.span
                  key="logo-text"
                  custom={0}
                  variants={itemVariants}
                  initial="hidden"
                  animate="visible"
                  exit="exit"
                  className="font-bold text-lg tracking-tighter whitespace-nowrap overflow-hidden pr-2 text-[color:var(--text-primary)]"
                >
                  ArchGuide.
                </motion.span>
              )}
            </AnimatePresence>
          </Link>

          {/* Desktop Nav Links */}
          <AnimatePresence>
            {isExpanded && (
              <motion.div
                key="nav-links"
                custom={0.15}
                variants={itemVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="hidden md:flex items-center gap-1 justify-center shrink-0 relative z-0 p-1"
              >
                {navLinks.map((link) => {
                  const isActive = activeTab === link.id;
                  return (
                    <Link
                      key={link.id}
                      href={link.href}
                      onClick={(e) => handleNavClick(e, link.href)}
                      className={`relative px-4 py-1.5 font-bold text-xs tracking-tight transition-all rounded-full z-10 flex items-center gap-1.5 ${isActive ? "text-[color:var(--background)]" : "text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"}`}
                    >
                      {link.name}
                      {link.id === "projects" && projectCount > 0 && (
                        <span className={`text-[9px] font-black px-1.5 py-0.5 rounded-full min-w-[18px] text-center leading-none ${isActive ? "bg-[color:var(--background)] text-[color:var(--text-primary)]" : "bg-[color:var(--text-primary)] text-[color:var(--background)]"}`}>
                          {projectCount}
                        </span>
                      )}
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

          {/* Actions (Right) */}
          <AnimatePresence>
            {isExpanded && (
              <motion.div
                key="nav-actions"
                custom={0.3}
                variants={itemVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="hidden md:flex items-center gap-2 shrink-0 relative z-10"
              >
                {/* Theme Toggle */}
                <button
                  onClick={(e) => { e.stopPropagation(); toggleTheme(); }}
                  className="w-8 h-8 flex items-center justify-center rounded-full bg-[color:var(--text-primary)]/5 border border-[color:var(--border)] text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all active:scale-90"
                >
                  {mounted ? (resolvedTheme === "dark" ? <Sun size={14} /> : <Moon size={14} />) : <div className="w-3.5 h-3.5" />}
                </button>

                {/* User Avatar, Sign In, or nothing */}
                {mounted ? (
                  user ? (
                    <div className="relative" ref={userMenuRef}>
                      <button
                        id="user-avatar-btn"
                        onClick={(e) => { e.stopPropagation(); setUserMenuOpen(!userMenuOpen); }}
                        className={`flex items-center gap-2 rounded-full border border-[color:var(--border)] bg-[color:var(--text-primary)]/5 hover:bg-[color:var(--text-primary)]/10 transition-all active:scale-95 ${phase === "top" ? "px-3 py-1.5" : "p-1"}`}
                      >
                        <div className={`${phase === "top" ? "w-5 h-5 text-[9px]" : "w-6 h-6 text-[10px]"} rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] flex items-center justify-center font-black shrink-0 transition-all`}>
                          {userInitial}
                        </div>
                        {phase === "top" && (
                          <span className="text-xs font-bold text-[color:var(--text-primary)] max-w-[80px] truncate pr-1">
                            {userFirstName}
                          </span>
                        )}
                      </button>

                      {/* Dropdown */}
                      <AnimatePresence>
                        {userMenuOpen && (
                          <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: -8 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: -8 }}
                            transition={{ type: "spring", stiffness: 400, damping: 30 }}
                            className="absolute right-0 top-[calc(100%+12px)] mt-0 w-48 rounded-2xl border border-[color:var(--border)] shadow-2xl overflow-hidden z-[9999]"
                            style={{ background: "var(--surface)", backdropFilter: "blur(20px)" }}
                          >
                            <div className="px-4 py-3 border-b border-[color:var(--border)]">
                              <p className="text-xs font-black text-[color:var(--text-primary)] truncate">{user.displayName || "User"}</p>
                              <p className="text-[10px] text-[color:var(--text-secondary)] truncate">{user.email}</p>
                            </div>
                            <Link
                              href="/projects"
                              onClick={() => setUserMenuOpen(false)}
                              className="flex items-center gap-2.5 px-4 py-3 text-xs font-bold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)]/5 transition-all"
                            >
                              <FolderOpen size={13} /> My Projects
                            </Link>
                            <button
                              id="sign-out-btn"
                              onClick={handleSignOut}
                              className="w-full flex items-center gap-2.5 px-4 py-3 text-xs font-bold text-red-500 hover:bg-red-500/10 transition-all"
                            >
                              <LogOut size={13} /> Sign Out
                            </button>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  ) : (
                    <button
                      onClick={() => setAuthModalOpen(true)}
                      className={`flex items-center gap-2 rounded-full border border-[color:var(--border)] bg-[color:var(--text-primary)] text-[color:var(--background)] hover:opacity-90 transition-all active:scale-95 ${phase === "top" ? "px-3 py-1.5" : "p-1.5"}`}
                    >
                      <User size={14} className={phase === "top" ? "w-3 h-3" : "w-4 h-4"} />
                      {phase === "top" && (
                        <span className="text-xs font-bold pr-1">Sign In</span>
                      )}
                    </button>
                  )
                ) : null}

                {/* Mobile toggle */}
                <button
                  onClick={(e) => { e.stopPropagation(); setIsMobileMenuOpen(!isMobileMenuOpen); }}
                  className="md:hidden w-8 h-8 flex items-center justify-center rounded-full text-[color:var(--text-primary)] active:scale-90 transition-transform"
                >
                  {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Mobile toggle only (when nav items exist) */}
          <AnimatePresence>
            {isExpanded && (
              <motion.div
                key="mobile-toggle"
                custom={0.3}
                variants={itemVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                className="flex md:hidden items-center gap-2 shrink-0 relative z-10"
              >
                <button
                  onClick={(e) => { e.stopPropagation(); toggleTheme(); }}
                  className="w-8 h-8 flex items-center justify-center rounded-full bg-[color:var(--text-primary)]/5 border border-[color:var(--border)] text-[color:var(--text-primary)] hover:bg-[color:var(--text-primary)] hover:text-[color:var(--background)] transition-all"
                >
                  {mounted ? (resolvedTheme === "dark" ? <Sun size={14} /> : <Moon size={14} />) : <div className="w-3.5 h-3.5" />}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setIsMobileMenuOpen(!isMobileMenuOpen); }}
                  className="w-8 h-8 flex items-center justify-center rounded-full text-[color:var(--text-primary)] active:scale-90 transition-transform"
                >
                  {isMobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Sphere Center Logo */}
          <AnimatePresence>
            {!isExpanded && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0, transition: { duration: 0.2 } }}
                className="absolute inset-0 flex items-center justify-center pointer-events-none"
              >
                <Hexagon size={24} className="text-[color:var(--text-primary)]" />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.nav>
      </div>

      {/* Mobile Menu */}
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
                        <span className={`text-[10px] font-black px-2 py-0.5 rounded-full ${isActive ? "bg-[color:var(--background)] text-[color:var(--text-primary)]" : "bg-[color:var(--text-primary)] text-[color:var(--background)]"}`}>
                          {projectCount}
                        </span>
                      )}
                    </Link>
                  </motion.div>
                );
              })}
            </div>

            {/* Mobile: User actions */}
            {user && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.35 }}
                className="flex flex-col gap-2"
              >
                <div className="flex items-center gap-3 px-6 py-3 rounded-full border border-[color:var(--border)] bg-[color:var(--surface)]">
                  <div className="w-7 h-7 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] flex items-center justify-center text-xs font-black">
                    {userInitial}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold truncate">{user.displayName}</p>
                    <p className="text-xs text-[color:var(--text-secondary)] truncate">{user.email}</p>
                  </div>
                </div>
                <button
                  onClick={handleSignOut}
                  className="flex items-center justify-center gap-2 w-full py-4 rounded-full border border-red-500/30 text-red-400 font-bold text-sm"
                >
                  <LogOut size={16} /> Sign Out
                </button>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}