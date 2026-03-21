# Echo Server and Bridge

## Current Split

- `api_server.py`
  - Runs the Python backend, WebSocket API, memory, tools, TTS orchestration, and vision pipeline.
- `frontend/main.js`
  - Starts the desktop shell in `desktop` mode.
- `frontend/main_bridge.js`
  - Starts the lightweight desktop shell in `bridge` mode.
- `frontend/admin.html`
  - Dedicated server admin page for runtime model configuration.
- `frontend/electron-shell.js`
  - Shared Electron bootstrap for both desktop and bridge modes.

## Bridge Behavior

- Bridge loads the local UI bundle instead of loading a remote HTML page.
- Bridge connects to a remote Echo server by address.
- Bridge hides runtime model configuration by default.
- Bridge does not push saved runtime model config to the server on startup.
- Bridge first exchanges the access token for a short-lived WebSocket ticket before connecting.
- Main client settings now only manage server address, observer mode, and access token.
- Runtime model configuration has moved to `/ui/admin.html`.

Use the admin page like this:

- If `ECHO_PUBLIC_UI=1`, open `https://your-server/ui/admin.html`
- If `ECHO_PUBLIC_UI=0`, open `http://127.0.0.1:18000/ui/admin.html` on the server itself

## Supported Server Address Formats

- `127.0.0.1:18000`
- `http://192.168.1.20:18000`
- `https://echo.example.com`
- `wss://echo.example.com`

If no protocol is provided:

- local/private addresses default to `http` / `ws`
- public domains default to `https` / `wss`

## Frontend Scripts

Run from `frontend/`:

```bash
npm run start:desktop
```

```bash
npm run start:bridge
```

```bash
npm run dist:desktop
```

```bash
npm run dist:bridge
```

## Bridge Startup Options

Bridge can receive the remote server address from:

- environment variable: `ECHO_BRIDGE_SERVER`
- CLI argument: `--server=https://echo.example.com`

Example:

```bash
ECHO_BRIDGE_SERVER=https://echo.example.com npm run start:bridge
```

## Next Recommended Steps

1. Add a bridge-first settings UX with explicit "Server URL" wording.
2. Add server-side auth for WebSocket and runtime config routes.
3. Split runtime config management into a server admin view instead of bridge UI.
4. Add bridge packaging assets, icon, and installer naming.
5. Add a health check / reconnect screen for remote deployments.

## Security Environment Variables

- `ECHO_ACCESS_TOKEN`
  - Required for `ws/chat` and protected read endpoints when set.
- `ECHO_WS_TICKET_TTL_SECONDS`
  - Lifetime for temporary WebSocket tickets. Default is `60`.
- `ECHO_ADMIN_TOKEN`
  - Required for runtime config writes.
- `ECHO_CORS_ORIGINS`
  - Comma-separated trusted browser origins such as `https://echo.example.com`.
- `ECHO_PUBLIC_HEALTH=1`
  - Makes `/health` public. Default is protected.
- `ECHO_PUBLIC_UI=0`
  - Disables remote access to `/` and `/ui`. Recommended for Bridge-only deployments.
