import { loginWithFeishu, readSavedGatewayToken } from './auth-flow.js';

export const CLIENT_VERSION = '0.1.4';

export function gatewayBaseUrl() {
  return (process.env.PARQUET_GATEWAY_URL || 'http://127.0.0.1:8080').replace(/\/+$/, '');
}

export async function resolveGatewayToken({ autoLogin = true } = {}) {
  const token = process.env.PARQUET_GATEWAY_TOKEN;
  if (token) return token;
  const savedToken = await readSavedGatewayToken();
  if (savedToken) return savedToken;
  if (!autoLogin) throw new Error('PARQUET_GATEWAY_TOKEN is required');
  const payload = await loginWithFeishu({ gatewayUrl: gatewayBaseUrl() });
  const loginToken = payload.access_token;
  if (!loginToken) throw new Error('Feishu login did not return PARQUET_GATEWAY_TOKEN');
  return loginToken;
}

async function gatewayToken() {
  const token = await resolveGatewayToken();
  return token;
}

export async function gatewayRequest(path, options = {}) {
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'X-Parquet-Client-Version': CLIENT_VERSION,
  };
  if (options.auth !== false) {
    headers.Authorization = `Bearer ${await gatewayToken()}`;
  }
  const response = await fetch(`${gatewayBaseUrl()}${path}`, {
    method: options.method || 'GET',
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = payload?.error?.message || payload?.detail || response.statusText;
    throw new Error(`Gateway HTTP ${response.status}: ${message}`);
  }
  warnIfClientOutdated(response);
  return payload;
}

function warnIfClientOutdated(response) {
  if (response.headers?.get('X-Parquet-Client-Version-Status') !== 'outdated') return;
  const latestVersion = response.headers.get('X-Parquet-Client-Latest-Version') || 'unknown';
  const downloadUrl = absoluteGatewayUrl(response.headers.get('X-Parquet-Client-Download-Url'));
  const guideUrl = absoluteGatewayUrl(response.headers.get('X-Parquet-Client-Guide-Url'));
  const guideSuffix = guideUrl ? ` (guide: ${guideUrl})` : '';
  const updateTarget = downloadUrl || 'ask your gateway administrator for the latest client package';
  console.error(`Parquet Gateway client ${CLIENT_VERSION} is older than server latest ${latestVersion}. Update: ${updateTarget}${guideSuffix}`);
}

function absoluteGatewayUrl(pathOrUrl) {
  if (!pathOrUrl) return '';
  return new URL(pathOrUrl, `${gatewayBaseUrl()}/`).toString();
}

export function splitCsv(value) {
  if (!value) return [];
  return value.split(',').map((part) => part.trim()).filter(Boolean);
}

const filterPattern = /^([A-Za-z_][A-Za-z0-9_]*)(>=|<=|!=|=|>|<| contains | startswith | in )(.+)$/;

export function parseFilter(expr) {
  const match = String(expr || '').trim().match(filterPattern);
  if (!match) throw new Error(`Invalid --where expression: ${expr}`);
  const [, field, rawOp, rawValue] = match;
  return { field, op: rawOp.trim(), value: parseValue(rawValue.trim()) };
}

export function parseValue(raw) {
  if (raw.startsWith('[')) return JSON.parse(raw);
  if ((raw.startsWith('"') && raw.endsWith('"')) || (raw.startsWith("'") && raw.endsWith("'"))) {
    return raw.slice(1, -1);
  }
  if (raw === 'true') return true;
  if (raw === 'false') return false;
  const numberValue = Number(raw);
  return Number.isNaN(numberValue) ? raw : numberValue;
}

export function parseAggregate(expr) {
  const parts = String(expr || '').split(':');
  if (parts.length !== 3) throw new Error(`Invalid --aggregate expression: ${expr}`);
  const [func, field, alias] = parts;
  const payload = { func, as: alias };
  if (field) payload.field = field;
  return payload;
}

export function parseOrderBy(expr) {
  if (!expr) return [];
  const parts = String(expr).split(':');
  if (parts.length === 1) return [{ field: parts[0], direction: 'asc' }];
  if (parts.length === 2 && ['asc', 'desc'].includes(parts[1])) {
    return [{ field: parts[0], direction: parts[1] }];
  }
  throw new Error(`Invalid --order-by expression: ${expr}`);
}
