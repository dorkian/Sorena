# Product

## Register

product

## Users

Ash — a developer running Sorena on their own Windows desktop as a daily hands-free/text assistant, and showing it to interviewers as a portfolio piece. One user, one machine, ambient use: the face is often open on a second monitor while they work.

## Product Purpose

Sorena is a local-first, $0/month Jarvis-style AI assistant: voice pipeline (wake word → STT → agent loop → streaming TTS), a multi-agent orchestrator with named Persian personas, long-term memory/RAG, and MCP integration. The UI is its face: it must show what the assistant is doing (idle / listening / thinking / speaking, and *which* agent is active) at a glance from across the room, and let the user converse by text when speaking isn't appropriate. Success = the state is legible instantly, the transcript is trustworthy, and it visibly demonstrates the Python backend working live.

## Brand Personality

Composed, mythic, precise. Persian-heritage naming (Sorena the general and their specialists) carried by color and identity, not ornament. Feels like a calm command room, not a chatbot toy.

## Anti-references

- Generic SaaS chat widgets (rounded-bubble candy chat, gradient CTAs).
- Sci-fi HUD kitsch: scanlines, fake radar rings, glitch text, "JARVIS ONLINE" cosplay.
- Cream/paper AI-default landing aesthetics — this is a dark ambient tool surface.

## Design Principles

1. **State is the product.** The orb and status line are the primary UI; everything else supports reading the assistant's state instantly.
2. **The personas are the palette.** Accent color always means "this agent is active" — never decoration.
3. **Local-first, zero-network.** No CDN fonts/scripts; system fonts, inline everything; works from file:// offline.
4. **Ambient-legible.** Readable from a distance in a dim room; dark surface, high-contrast text, calm motion.
5. **Honest transcript.** What was heard and what was said, verbatim, with clear attribution.

## Accessibility & Inclusion

WCAG AA contrast (≥4.5:1 body text). Full `prefers-reduced-motion` support (orb freezes to a static sphere, transitions become crossfades). All controls keyboard-operable; live status announced via `aria-live`.
