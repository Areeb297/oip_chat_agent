# OIP Assistant Chat UI

A modern, embeddable chatbot interface for the Ebttikar Operations Intelligence Platform (OIP) built with Next.js 15 and ShadCN UI.

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 16.x | React framework with App Router |
| React | 19.x | UI library |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 4.x | Utility-first styling |
| ShadCN UI | Latest | Component library |
| Lucide React | Latest | Icon system |

## Features

- **Floating Chat Widget** - Embeddable popup chat in bottom-right corner
- **Full-Screen Chat** - Dedicated `/chat` page with conversation sidebar
- **SSE Streaming** - Real-time streaming responses from Google ADK backend
- **Chat History** - Persistent local storage for conversation history
- **OIP Branding** - Colors matching the OIP application design
- **Responsive Design** - Works on desktop and mobile

## Getting Started

### Prerequisites

- Node.js 18+
- npm or pnpm
- Backend server running at `http://localhost:8080`

### Installation

```bash
# Install dependencies
npm install

# Create environment file
cp .env.local.example .env.local
# Edit .env.local with your backend URL
```

### Development

```bash
# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### Production Build

```bash
# Build for production
npm run build

# Start production server
npm start
```

## Project Structure

```
src/
├── app/
│   ├── page.tsx              # Landing page with embedded widget
│   ├── chat/page.tsx         # Full-screen chat interface
│   ├── layout.tsx            # Root layout with fonts
│   └── globals.css           # OIP theme CSS variables
│
├── components/
│   ├── chatbot/              # Chat components
│   │   ├── ChatWidget.tsx    # Floating widget container
│   │   ├── ChatIcon.tsx      # FAB button
│   │   ├── ChatPopup.tsx     # Popup window
│   │   ├── ChatHeader.tsx    # Header with actions
│   │   ├── ChatMessages.tsx  # Message list
│   │   ├── ChatMessage.tsx   # Single message bubble
│   │   ├── ChatInput.tsx     # Input field + send
│   │   ├── ChatSidebar.tsx   # History sidebar
│   │   ├── ChatFullScreen.tsx# Full-page chat
│   │   ├── TypingIndicator.tsx
│   │   └── index.ts          # Exports
│   │
│   └── ui/                   # ShadCN UI components
│       ├── button.tsx
│       ├── card.tsx
│       ├── input.tsx
│       ├── scroll-area.tsx
│       ├── avatar.tsx
│       └── tooltip.tsx
│
├── hooks/
│   ├── useChat.ts            # Chat state & SSE streaming
│   ├── useChatHistory.ts     # LocalStorage persistence
│   └── index.ts
│
├── lib/
│   ├── api.ts                # Backend API client
│   └── utils.ts              # cn() and helpers
│
├── config/
│   └── api.config.ts         # API endpoints config
│
└── types/
    └── chat.ts               # TypeScript interfaces
```

## Usage

### Embed the Chat Widget

Add the floating chat widget to any page:

```tsx
import { ChatWidget } from '@/components/chatbot';

export default function MyPage() {
  return (
    <div>
      {/* Your page content */}
      <ChatWidget
        position="bottom-right"
        defaultOpen={false}
      />
    </div>
  );
}
```

### Widget Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `position` | `'bottom-right' \| 'bottom-left'` | `'bottom-right'` | Widget position |
| `defaultOpen` | `boolean` | `false` | Open by default |
| `sessionId` | `string` | Auto-generated | Resume session |
| `onExpandClick` | `() => void` | Navigate to /chat | Expand handler |
| `onNewSession` | `(id: string) => void` | - | New session callback |

### Direct Component Usage

```tsx
import {
  ChatMessages,
  ChatInput,
  ChatHeader
} from '@/components/chatbot';
import { useChat } from '@/hooks';

export default function CustomChat() {
  const { messages, isLoading, sendMessage } = useChat();

  return (
    <div className="flex flex-col h-screen">
      <ChatHeader title="My Chat" />
      <ChatMessages messages={messages} isLoading={isLoading} />
      <ChatInput onSend={sendMessage} isLoading={isLoading} />
    </div>
  );
}
```

## API Integration

The frontend connects to the FastAPI backend via:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Simple chat (non-streaming) |
| `/run_sse` | POST | Streaming chat (SSE) |
| `/session/new` | POST | Create new session |
| `/health` | GET | Health check |

### Configuration

Edit `src/config/api.config.ts` or set environment variable:

```env
NEXT_PUBLIC_API_URL=http://localhost:8080
```

## Theming

The UI uses OIP brand colors (single light theme) defined in `globals.css`:

| Variable | Value | Usage |
|----------|-------|-------|
| `--primary` | `#3b82f6` | Buttons, links, accents |
| `--sidebar` | `#1e293b` | Dark navigation header |
| `--background` | `#f8fafc` | Page background |
| `--card` | `#ffffff` | Card backgrounds |
| `--muted` | `#f1f5f9` | Muted backgrounds |
| `--chart-1` | `#3b82f6` | Blue (primary) |
| `--chart-2` | `#22c55e` | Green (closed/approved) |
| `--chart-3` | `#f97316` | Orange (open/warning) |
| `--chart-4` | `#eab308` | Yellow (pending) |

To customize, edit the CSS variables in `src/app/globals.css` or use [Tweakcn](https://tweakcn.com/editor/theme) to generate new values.

## Scripts

```bash
npm run dev      # Start dev server
npm run build    # Production build
npm run start    # Start production
npm run lint     # Run ESLint
```

## License

Internal use - Ebttikar Technology
