# Task 5: Frontend Scaffold

**Files:**
- Create: `frontend/` (via Vite scaffold)
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/types/graph.ts`
- Create: `frontend/src/services/api.ts`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/Dockerfile`

---

- [ ] **Step 1: Scaffold Vite + React + TypeScript**

```bash
npm create vite@latest frontend -- --template react-ts
```

- [ ] **Step 2: Install dependencies**

```bash
cd frontend
npm install @xyflow/react motion tailwind-merge clsx axios
npm install -D tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: Configure Tailwind v4 with dark mode**

Tailwind v4 uses CSS-first config. Create `src/index.css`:
```css
@import "tailwindcss";
```

Update `vite.config.ts` to use `@tailwindcss/vite` plugin.

- [ ] **Step 4: Initialize shadcn/ui**

```bash
npx shadcn@latest init
```

Select: TypeScript, default style, CSS variables, dark mode class strategy.

- [ ] **Step 5: Create TypeScript types matching backend models**

```typescript
// src/types/graph.ts
export type NodeType = 'news_event' | 'impact' | 'stock_endpoint'
  | 'value_opportunity' | 'reason' | 'convergence';
export type Direction = 'bullish' | 'bearish' | 'neutral';
export type Market = 'CN' | 'US';

export interface GraphNode {
  id: string;
  type: NodeType;
  surface_summary: string;
  direction: Direction;
  confidence: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

export interface DailyGraph {
  date: string;
  market: Market;
  status: 'pending' | 'complete' | 'failed';
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Layer {
  node_id: string;
  depth: 0 | 1 | 2 | 3;
  content: string;
  tool_outputs?: Record<string, unknown>;
  sources?: string[];
}
```

- [ ] **Step 6: Create API service with axios**

```typescript
// src/services/api.ts
import axios from 'axios';
import type { DailyGraph, Layer } from '../types/graph';

const api = axios.create({ baseURL: '/api' });

export const graphApi = {
  getGraph: (date: string, market = 'US') =>
    api.get<DailyGraph>(`/graphs/${date}`, { params: { market } }),
  getDates: () =>
    api.get<string[]>('/graphs/dates'),
  getNodeLayers: (nodeId: string) =>
    api.get<Layer[]>(`/nodes/${nodeId}/layers`),
};
```

- [ ] **Step 7: Create cn() utility**

```typescript
// src/lib/utils.ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 8: Create minimal App.tsx with React Flow placeholder**

Dark background, full viewport React Flow canvas with empty state message.
TopBar with logo text + date placeholder. BottomBar with placeholder buttons.

- [ ] **Step 9: Create frontend Dockerfile**

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json .
RUN npm install
COPY . .
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 10: Verify `npm run dev` shows the dark-themed shell**

- [ ] **Step 11: Commit**

```bash
git commit -m "feat: frontend scaffold — Vite, Tailwind v4, React Flow, shadcn, Motion"
```
