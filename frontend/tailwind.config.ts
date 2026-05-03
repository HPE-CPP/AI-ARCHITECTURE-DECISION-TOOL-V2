import type { Config } from "tailwindcss";
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Plus Jakarta Sans'", "'DM Sans'", "Inter", "sans-serif"],
        display: ["'Clash Display'", "'Space Grotesk'", "sans-serif"],
        mono: ["'JetBrains Mono'", "'Fira Code'", "monospace"],
      },
      colors: {
        primary: "#01A982",
        accent:  "#0A84FF",
        purple:  "#7F35B2",
        orange:  "#FF8300",
      },
    },
  },
  plugins: [],
};
export default config;
