# HealthFlow Frontend - Chat Interface

React-based chat interface for the HealthFlow RCM multi-agent system.

## Features

- **Real-time Chat:** WebSocket-based real-time messaging
- **Voice Input:** Record and transcribe voice messages
- **File Upload:** Upload documents for OCR processing
- **Multi-Agent Support:** Interact with different AI agents
- **Typing Indicators:** See when agents are responding
- **Message History:** Persistent conversation history
- **Responsive Design:** Works on desktop and mobile

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Material-UI (MUI)** - Component library
- **Vite** - Build tool
- **Zustand** - State management
- **Axios** - HTTP client
- **WebSocket** - Real-time communication

## Prerequisites

- Node.js 18+ and npm/pnpm
- Backend API running on `http://localhost:8000`

## Installation

```bash
# Install dependencies
npm install

# or with pnpm
pnpm install
```

## Configuration

Create a `.env` file in the `frontend/` directory:

```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

## Development

```bash
# Start development server
npm run dev

# Server runs on http://localhost:5173
```

## Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/          # React components
│   │   ├── ChatInterface.tsx    # Main chat UI
│   │   ├── MessageBubble.tsx    # Message display
│   │   ├── VoiceRecorder.tsx    # Voice recording
│   │   └── FileUploader.tsx     # File upload
│   ├── services/            # API & WebSocket services
│   │   ├── api.service.ts       # REST API client
│   │   └── websocket.service.ts # WebSocket client
│   ├── store/               # State management
│   │   └── chat.store.ts        # Chat state (Zustand)
│   ├── types/               # TypeScript types
│   │   └── chat.types.ts        # Chat-related types
│   ├── App.tsx              # Main app component
│   ├── main.tsx             # Entry point
│   └── index.css            # Global styles
├── package.json
├── tsconfig.json
├── vite.config.ts
└── index.html
```

## Components

### ChatInterface
Main chat interface component that orchestrates all other components.

**Features:**
- Message list with auto-scroll
- Input field with send button
- Voice recording toggle
- File upload toggle
- Connection status indicator

### MessageBubble
Displays individual chat messages with different styles for user/assistant.

**Features:**
- User/Assistant styling
- Timestamp display
- Agent name display
- Markdown rendering (future)

### VoiceRecorder
Records audio and sends to backend for transcription.

**Features:**
- Start/stop recording
- Waveform visualization
- Audio preview
- Automatic upload

### FileUploader
Handles file uploads with drag-and-drop support.

**Features:**
- Drag-and-drop
- File preview
- Upload progress
- File type validation

## State Management

Using **Zustand** for simple, efficient state management:

```typescript
const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isConnected: false,
  isTyping: false,
  typingAgent: null,
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  // ... more actions
}))
```

## API Integration

### REST API (api.service.ts)
```typescript
// Get current user
const user = await apiService.getCurrentUser()

// Get conversation history
const history = await apiService.getConversationHistory(conversationId)

// Upload file
const result = await apiService.uploadFile(file)
```

### WebSocket (websocket.service.ts)
```typescript
// Connect
await websocketService.connect(userId)

// Send message
websocketService.sendMessage(message)

// Listen for messages
websocketService.onMessage((message) => {
  console.log('New message:', message)
})
```

## Styling

Using **Material-UI** components with custom theme:

```typescript
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
})
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `http://localhost:8000` |
| `VITE_WS_URL` | WebSocket URL | `ws://localhost:8000` |

## Troubleshooting

### WebSocket Connection Issues
```bash
# Check if backend is running
curl http://localhost:8000/health

# Check WebSocket endpoint
wscat -c ws://localhost:8000/api/v1/chat/ws?token=YOUR_TOKEN
```

### Build Errors
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Vite cache
rm -rf .vite
```

### CORS Issues
Ensure backend has CORS configured for `http://localhost:5173`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Testing

```bash
# Run tests (when configured)
npm run test

# Run tests with coverage
npm run test:coverage
```

## Deployment

### Build for Production
```bash
npm run build
# Output in dist/
```

### Deploy to Vercel
```bash
npm install -g vercel
vercel --prod
```

### Deploy to Netlify
```bash
npm install -g netlify-cli
netlify deploy --prod
```

### Serve with Nginx
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    root /path/to/frontend/dist;
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## Performance

- **Code Splitting:** Vite automatically splits code
- **Lazy Loading:** Components loaded on demand
- **Asset Optimization:** Images and fonts optimized
- **Caching:** Service worker for offline support (future)

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Create feature branch
2. Make changes
3. Test thoroughly
4. Submit pull request

## License

Proprietary - HealthFlow Egypt

## Support

For issues or questions, contact the development team.

