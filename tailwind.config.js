/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
    "./*.html"
  ],
  theme: {
    extend: {
      colors: {
        'trading-green': '#10b981',
        'trading-red': '#ef4444',
        'trading-blue': '#667eea',
        'trading-yellow': '#f59e0b',
      }
    }
  },
  daisyui: {
    themes: [
      {
        dark: {
          "primary": "#667eea",
          "secondary": "#764ba2",
          "accent": "#f59e0b",
          "neutral": "#1a1a2e",
          "base-100": "#0a0e27",
          "info": "#3b82f6",
          "success": "#10b981",
          "warning": "#f59e0b",
          "error": "#ef4444",
        },
      },
      "light",
      "garden"
    ],
    darkTheme: "dark",
    base: true,
    styled: true,
    utils: true,
    prefix: "",
    logs: true,
  },
  plugins: [require("daisyui")]
}