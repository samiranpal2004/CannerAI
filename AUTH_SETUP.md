# Authentication Flow Configuration

## Environment Setup

### Running Flask Backend Locally
When running Flask directly with Python (not in Docker):
```bash
cd backend
source .env.development  # or use python-dotenv
python app.py
```

Uses `.env.development` with:
- `AUTH_BACKEND_URL=http://localhost:3000`

### Running Flask Backend in Docker
When running Flask in Docker:
```bash
docker compose up
```

Uses `.env.docker` with:
- `AUTH_BACKEND_URL=http://host.docker.internal:3000`

## Complete Auth Flow

```
Extension (port: chrome-extension://)
    ↓
Flask Backend (port 5000)
    ↓ (redirects user browser)
Next.js Frontend (port 3000) - User Login UI
    ↓ (generates auth code, redirects back)
Extension Auth Callback
    ↓ (sends auth code)
Flask Backend (port 5000)
    ↓ (validates code)
Next.js API (port 3000)
    ↓ (proxies to)
FastAPI Backend (port 8000) - Validates and returns user_id
    ↓ (returns user_id)
Flask Backend (port 5000) - Generates JWT
    ↓ (returns JWT)
Extension - Stores credentials
```

## Environment Variables

### Backend (.env.development / .env.docker)
- `DATABASE_URL`: MongoDB connection string
- `AUTH_BACKEND_URL`: Where Flask calls for auth validation
- `AUTH_FRONTEND_URL`: Where browser is redirected for login
- `JWT_SECRET_KEY`: Secret for JWT token generation
- `GEMINI_API_KEY`: API key for Gemini

### Extension (configured in webpack)
- `REACT_APP_BACKEND_URL`: Flask backend URL (default: http://localhost:5000)

## Important Notes

1. **No hardcoded URLs** - All URLs come from environment variables
2. **Separate configs** - Different env files for local vs Docker
3. **Docker networking** - Use `host.docker.internal` from Docker to access host services
4. **Browser URLs** - Always use `localhost` for browser redirects
