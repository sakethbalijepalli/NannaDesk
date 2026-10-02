/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        paper: { DEFAULT: "#EDE6D6", dark: "#191B20" },
        ink: { DEFAULT: "#1F2A44", light: "#9FB0E0" },
        margin: "#A13D2E",
        stamp: "#3F6B4A",
        gold: "#B8862E",
      },
      fontFamily: {
        display: ["Fraunces", "Noto Serif Telugu", "serif"],
        body: ["Public Sans", "Noto Sans Telugu", "sans-serif"],
      },
      fontSize: {
        base: ["1.125rem", "1.65"],
        lg: ["1.3rem", "1.6"],
        xl: ["1.6rem", "1.5"],
        "2xl": ["2.1rem", "1.3"],
      },
      keyframes: {
        "write-in": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        stamp: {
          "0%": { opacity: "0", transform: "scale(1.6) rotate(-8deg)" },
          "60%": { opacity: "1", transform: "scale(0.95) rotate(-8deg)" },
          "100%": { opacity: "1", transform: "scale(1) rotate(-8deg)" },
        },
      },
      animation: {
        "write-in": "write-in 0.5s ease-out both",
        stamp: "stamp 0.35s cubic-bezier(.2,.9,.3,1.3) both",
      },
    },
  },
  plugins: [],
};
