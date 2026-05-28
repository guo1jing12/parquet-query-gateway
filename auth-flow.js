import { createServer } from 'node:http';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { spawn } from 'node:child_process';

export const DEFAULT_REDIRECT_URI = 'http://127.0.0.1:8765/callback';
export const DEFAULT_TOKEN_PATH = join(homedir(), '.parquet-gateway', 'token.json');

export function tokenPath() {
  return process.env.PARQUET_GATEWAY_TOKEN_PATH || DEFAULT_TOKEN_PATH;
}

export async function readSavedGatewayToken(path = tokenPath()) {
  try {
    const raw = await readFile(path, 'utf-8');
    const payload = JSON.parse(raw);
    return payload.access_token || '';
  } catch (err) {
    if (err?.code === 'ENOENT') return '';
    throw err;
  }
}

export async function discoverFeishuAuthUrl({ gatewayUrl, redirectUri }) {
  if (process.env.PARQUET_FEISHU_AUTH_URL) {
    return process.env.PARQUET_FEISHU_AUTH_URL;
  }
  const url = new URL('/auth/feishu/authorize-url', gatewayUrl);
  url.searchParams.set('redirect_uri', redirectUri);
  const response = await fetch(url);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = payload?.error?.message || payload?.detail || response.statusText;
    throw new Error(`Feishu login is not available from gateway: ${message}`);
  }
  if (!payload.auth_url) {
    throw new Error('Gateway did not return a Feishu authorization URL');
  }
  return payload.auth_url;
}

export async function loginWithFeishu({
  gatewayUrl,
  authUrl,
  redirectUri = process.env.PARQUET_FEISHU_REDIRECT_URI || DEFAULT_REDIRECT_URI,
  timeoutSeconds = 180,
  savePath = tokenPath(),
} = {}) {
  const actualAuthUrl = authUrl || await discoverFeishuAuthUrl({ gatewayUrl, redirectUri });
  const code = await loginViaBrowser({
    authUrl: actualAuthUrl,
    redirectUri,
    timeoutSeconds,
  });
  const payload = await exchangeFeishuCode({
    gatewayUrl,
    code,
    redirectUri,
  });
  await saveGatewayToken(savePath, payload);
  return payload;
}

export async function exchangeFeishuCode({ gatewayUrl, code, redirectUri }) {
  const response = await fetch(new URL('/auth/feishu/exchange', gatewayUrl), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ code, redirect_uri: redirectUri }),
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = payload?.error?.message || payload?.detail || response.statusText;
    throw new Error(`Gateway HTTP ${response.status}: ${message}`);
  }
  return payload;
}

export async function loginViaBrowser({ authUrl, redirectUri, timeoutSeconds }) {
  if (!authUrl) {
    throw new Error('PARQUET_FEISHU_AUTH_URL, --auth-url, or gateway Feishu auth configuration is required when code is not provided');
  }
  const callbackPromise = waitForCallbackCode({ redirectUri, timeoutSeconds });
  console.error(`Open this Feishu authorization URL if your browser does not open automatically:\n${authUrl}`);
  openBrowser(authUrl);
  return await callbackPromise;
}

function waitForCallbackCode({ redirectUri, timeoutSeconds }) {
  const parsed = new URL(redirectUri);
  const host = parsed.hostname;
  const port = Number(parsed.port || 80);
  const expectedPath = parsed.pathname;

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      server.close();
      reject(new Error(`Timed out waiting for Feishu callback after ${timeoutSeconds}s`));
    }, timeoutSeconds * 1000);

    const server = createServer((req, res) => {
      try {
        const url = new URL(req.url || '/', redirectUri);
        if (url.pathname !== expectedPath) {
          res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
          res.end('Not Found');
          return;
        }
        const error = url.searchParams.get('error');
        if (error) throw new Error(`Feishu authorization failed: ${error}`);
        const code = url.searchParams.get('code');
        if (!code) throw new Error('Feishu callback did not include code');
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end('<html><body>Parquet Gateway login complete. You can close this window.</body></html>');
        clearTimeout(timer);
        server.close();
        resolve(code);
      } catch (err) {
        clearTimeout(timer);
        server.close();
        reject(err);
      }
    });

    server.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
    server.listen(port, host);
  });
}

function openBrowser(url) {
  const platform = process.platform;
  const command = platform === 'win32' ? 'powershell.exe' : platform === 'darwin' ? 'open' : 'xdg-open';
  const args = platform === 'win32'
    ? ['-NoProfile', '-Command', 'Start-Process', '-FilePath', url]
    : [url];
  const child = spawn(command, args, { detached: true, stdio: 'ignore' });
  child.unref();
}

export async function saveGatewayToken(path, payload) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify({
    access_token: payload.access_token,
    token_type: payload.token_type,
    expires_in: payload.expires_in,
    saved_at: new Date().toISOString(),
  }, null, 2)}\n`, 'utf-8');
}
