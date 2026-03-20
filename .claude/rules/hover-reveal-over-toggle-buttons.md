# Hover-to-Reveal Over Toggle Buttons

## The Trap
Adding explicit toggle buttons in headers to show/hide side panels. Wastes header space and adds unnecessary clicks.

## The Solution
Use hover-to-reveal on screen edges — panel collapses to `w-0` and expands on hover with CSS transition. No button needed.

```css
.panel { transition: width 0.3s; }
/* collapsed by default, expands on hover */
```

## Context
- **When this applies:** Any collapsible side panel in the UI
- **Related files:** `frontend/src/App.tsx`
- **Discovered:** 2026-03-20, user corrected toggle button approach — "it should be hover the side to show. That's way easier."
