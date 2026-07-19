/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        void: '#080c10', // Deep navy-black
        panel: 'rgba(15, 23, 36, 0.85)', // Frosted glass panels
        borderLine: 'rgba(0, 212, 255, 0.3)', // Cyber borders
        primary: '#00d4ff', // Cyan
        secondary: '#a78bfa', // Violet
        phosphor: '#39ff6a',
        amber: '#ffb020',
        steel: '#cbd5e1'
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['Inter', 'sans-serif']
      }
    },
  },
  plugins: [],
}
