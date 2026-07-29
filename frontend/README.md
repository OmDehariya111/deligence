# DeligenX Launchpad

Build the foundation and landing page hero for "DeligenX" — an autonomous AI financial due diligence platform that turns any US public company ticker into a full institutional-grade investment memorandum in minutes, fully autonomously, with zero human intervention between input and output.

THIS IS A HACKATHON DEMO (IITISoC 2026) that needs to look and feel like a funded, category-defining Series A fintech product — think the visual confidence of Linear, Vercel, and Stripe's marketing sites, crossed with the data-density authority of a Bloomberg Terminal, rendered in a premium dark theme. Judges should feel like they're looking at a real company, not a student project.

=== BRAND IDENTITY ===
Name: DeligenX
Tagline: "Autonomous due diligence. Institutional grade. Minutes, not weeks."
Tone: Confident, technical, precise. No fluffy startup-speak. Write copy the way a quant hedge fund would write it — specific numbers, specific model names (Beneish M-Score, Altman Z-Score), no vague "AI-powered synergy" language.

=== VISUAL SYSTEM ===
Theme: Pure dark mode, no light mode toggle needed.
- Background: near-black (#0A0A0A base, #050505 for deepest sections, #111111 for elevated cards) — never pure #000000, it should have subtle warmth/depth
- Primary accent: neon green (#39FF88 as the hero accent, with a brighter #4DFFA0 for hover/glow states and a deep #0F3D26 for tinted backgrounds/borders)
- Secondary accent: amber-red (#FF5C5C / #FFB020) used ONLY for risk indicators, warnings, and negative deltas — never for primary UI
- Text: off-white (#F5F5F5) for primary text, (#A0A0A0) for secondary/muted text, never pure white
- Borders: hairline 1px borders at low opacity white (rgba(255,255,255,0.08)), glowing neon green border on hover/focus states
- Glassmorphism: frosted glass cards (backdrop-blur, semi-transparent dark background, subtle border) for navbar, modals, and floating panels
- Subtle noise/grain texture overlay on the background for premium film-like depth (very low opacity, like Linear/Vercel use)
- Gradient mesh glows: soft, large, blurred neon-green radial gradients bleeding in from corners of the hero section — this is the single most important "premium" visual signal, do not skip it

Typography:
- Headings: a clean geometric sans-serif with tight tracking (Inter, Geist, or General Sans — bold weights, large scale, tight letter-spacing on big headlines)
- Body: same family, regular weight, comfortable line-height
- Numbers/data/tickers/code: a monospace font (JetBrains Mono or Space Mono) — use this specifically for anything that looks like financial data (stock prices, percentages, scores, tickers) to give it that terminal/quant authenticity
- Massive hero headline scale (clamp responsive, ~64-96px desktop), tight line-height, gradient text fill (white to neon green) on the key phrase

Icons: Lucide icons throughout, thin stroke weight, consistent sizing.

=== NAVBAR ===
Sticky, glassmorphic (blurred dark background, becomes more opaque on scroll), thin bottom border that glows faintly neon green.
Left: DeligenX logo mark (a minimal geometric icon — abstract interlocking nodes/hexagon suggesting a neural network — plus wordmark in the mono font).
Center/right nav links: Product, How It Works, Live Demo, Pricing, About.
Right: a ghost-outline "Sign In" button and a solid neon-green "Try Free Demo" button with a subtle glow/pulse animation on the button border.
Mobile: clean hamburger menu that slides in as a full-screen glassmorphic overlay.

=== HERO SECTION ===
Full viewport height. Structure:
1. A small pill/badge above the headline: "● Autonomous 5-Agent AI Pipeline" with a pulsing neon-green dot, glassmorphic pill background
2. Massive headline (2 lines): "Investment memos that write themselves." with "write themselves" in a neon-green gradient
3. Subheadline below in muted gray: "DeligenX ingests SEC filings, runs deterministic financial models, scores six dimensions of risk, and produces a fully-cited investment memorandum — autonomously, in minutes."
4. A ticker input field styled like a terminal command bar: monospace font, a blinking cursor placeholder like "AAPL_", a neon-green "Analyze" button beside it with an arrow icon — make this feel interactive and alive even though it doesn't need to be wired to a backend yet, just visually convincing with a hover/focus glow
5. Below that, small trust row: "Powered by SEC EDGAR · yfinance · FRED · Real-time filing data" in muted mono text with small icons

=== THE 3D CENTERPIECE (critical — build this carefully) ===
Behind/beside the hero text (desktop: positioned right side or as a full-bleed background element; mobile: simplified or hidden), render an interactive 3D "Neural Orb" using Three.js / React Three Fiber (@react-three/fiber + @react-three/drei):

- A central glowing sphere/orb core, semi-transparent, wireframe or particle-based, neon green with emissive glow (bloom post-processing effect if feasible)
- Exactly 5 smaller glowing nodes orbiting the central orb at different radii/speeds, representing DeligenX's 5 AI agents (Ingestion, Analysis, Market Intelligence, Risk Assessment, Memo Generation) — on hover over the orb region, small labels can appear next to each node naming the agent
- Thin animated connecting lines/particles flowing between the 5 nodes and the central core, like data pulses traveling along neural pathways — these should pulse/travel continuously, suggesting constant agent-to-agent handoff
- AUTONOMOUS MOTION: the whole system should slowly auto-rotate on its own by default (slow, majestic, continuous — never stops)
- CURSOR INTERACTION: when the user moves their mouse over the hero area, the orb should subtly respond — tilt/rotate toward the cursor position (parallax-style, using mouse position mapped to rotation on X/Y axes), and on click-and-drag the user should be able to freely spin the orb in any direction with momentum/inertia (like a trackball), which then gently eases back into its idle auto-rotation after a moment of no interaction
- Add a soft bloom/glow post-processing pass so the neon green genuinely glows rather than looking like flat 3D geometry
- Performance: this must stay performant — use a reasonable particle/node count, and gracefully degrade to a simpler CSS/SVG animated version on mobile or low-power devices if full Three.js is too heavy

=== FOOTER ===
Dark, multi-column: Product links, Company links, Resources/Docs links, Social icons. Include a final CTA strip above the footer: "Ready to see it in action?" with a neon-green button. Small print at the very bottom: "© 2026 DeligenX · Built for IITISoC 2026 · Not investment advice."

Build this now as a complete, responsive, production-quality landing page hero + navbar + footer. Use smooth scroll-triggered fade/slide-up animations (Framer Motion) on all sections as they enter viewport.

This project was built with [Lovable](https://lovable.dev).

**Live app**: https://deligenx-ai-scribe.lovable.app

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/a80b2324-0417-4758-ba4a-e6cb23a8d489).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
