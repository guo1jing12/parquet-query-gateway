import { cli, Strategy } from '@jackwener/opencli/registry';
import { gatewayBaseUrl } from './gateway-client.js';
import {
  DEFAULT_REDIRECT_URI,
  exchangeFeishuCode,
  loginWithFeishu,
  saveGatewayToken,
  tokenPath,
} from './auth-flow.js';

cli({
  site: 'parquet',
  name: 'login',
  access: 'read',
  description: 'Log in with Feishu and save a gateway token',
  strategy: Strategy.LOCAL,
  browser: false,
  args: [
    { name: 'code', positional: true, required: false, help: 'Feishu OAuth authorization code' },
    { name: 'redirect-uri', help: 'Feishu redirect URI used for the authorization code' },
    { name: 'auth-url', help: 'Feishu authorization URL; defaults to PARQUET_FEISHU_AUTH_URL' },
    { name: 'token-path', help: 'Where to save the gateway token JSON' },
    { name: 'timeout', type: 'int', default: 180, help: 'Seconds to wait for local callback' },
  ],
  columns: ['token_path', 'token_type', 'expires_in', 'PARQUET_GATEWAY_TOKEN'],
  func: async (args) => {
    const redirectUri = args['redirect-uri'] || process.env.PARQUET_FEISHU_REDIRECT_URI || DEFAULT_REDIRECT_URI;
    const savePath = args['token-path'] || tokenPath();
    const payload = args.code
      ? await exchangeFeishuCode({
        gatewayUrl: gatewayBaseUrl(),
        code: args.code,
        redirectUri,
      })
      : await loginWithFeishu({
        gatewayUrl: gatewayBaseUrl(),
        authUrl: args['auth-url'] || process.env.PARQUET_FEISHU_AUTH_URL,
        redirectUri,
        timeoutSeconds: Number(args.timeout || 180),
        savePath,
      });
    if (args.code) {
      await saveGatewayToken(savePath, payload);
    }
    return [{
      token_path: savePath,
      token_type: payload.token_type,
      expires_in: payload.expires_in,
      PARQUET_GATEWAY_TOKEN: payload.access_token,
    }];
  },
});
