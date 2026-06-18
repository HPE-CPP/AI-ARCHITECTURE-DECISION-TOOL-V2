/**
 * Vitest global test setup
 * Runs before every test file.
 */
import '@testing-library/jest-dom'
import { vi } from 'vitest'

// ─── Mock Next.js router ───────────────────────────────────────────────────
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    prefetch: vi.fn(),
    pathname: '/',
    query: {},
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/',
}))

// ─── Mock Firebase ─────────────────────────────────────────────────────────
vi.mock('@/lib/firebase', () => ({
  auth: {
    currentUser: null,
    onAuthStateChanged: vi.fn((cb) => { cb(null); return vi.fn() }),
    signInWithPopup: vi.fn(),
    signOut: vi.fn(),
  },
  googleProvider: {},
}))

// ─── Mock localStorage ─────────────────────────────────────────────────────
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = String(value) },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
  }
})()

Object.defineProperty(window, 'localStorage', { value: localStorageMock })
Object.defineProperty(window, 'scrollTo', { value: vi.fn() })

// ─── Global fetch mock (override per test) ─────────────────────────────────
global.fetch = vi.fn()

// ─── Clean up after each test ──────────────────────────────────────────────
afterEach(() => {
  vi.clearAllMocks()
  localStorageMock.clear()
})
