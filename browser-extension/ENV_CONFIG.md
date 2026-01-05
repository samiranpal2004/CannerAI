# Environment Configuration

## Configuration Variables

The extension uses one environment variable:

- **REACT_APP_BACKEND_URL** - Backend API URL (Flask server for all API operations including authentication)

## Environment Files

### Development (`.env.development`)
```env
REACT_APP_BACKEND_URL=http://localhost:5000
```

### Production (`.env.production`)
```env
REACT_APP_BACKEND_URL=https://api.cannerai.com
```

## Build Commands

```bash
# Development build
npm run build:dev

# Production build
npm run build

# Watch mode (auto-rebuild)
npm run dev
```

## Updating URLs

1. Edit `.env.development` or `.env.production`
2. Update the URLs
3. Run the appropriate build command
4. Reload the extension in Chrome

## How It Works

- `config.ts` reads environment variables at build time
- Webpack DefinePlugin injects values during compilation
- All API calls use the configured URLs

That's it! Simple and clean. 🎯
