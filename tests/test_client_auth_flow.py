from __future__ import annotations

import json
import subprocess


def run_node(script: str) -> str:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_gateway_client_reads_saved_login_token(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"access_token": "saved-token"}), encoding="utf-8")

    output = run_node(f"""
        process.env.PARQUET_GATEWAY_TOKEN = '';
        process.env.PARQUET_GATEWAY_TOKEN_PATH = {json.dumps(str(token_path))};
        const client = await import('./gateway-client.js');
        console.log(await client.resolveGatewayToken({{ autoLogin: false }}));
    """)

    assert output == "saved-token"


def test_auth_flow_discovers_feishu_authorize_url_from_gateway():
    output = run_node("""
        const calls = [];
        globalThis.fetch = async (url) => {
          calls.push(String(url));
          return {
            ok: true,
            status: 200,
            statusText: 'OK',
            text: async () => JSON.stringify({
              auth_url: 'https://open.feishu.cn/open-apis/authen/v1/authorize?app_id=cli_test',
            }),
          };
        };
        const auth = await import('./auth-flow.js');
        const url = await auth.discoverFeishuAuthUrl({
          gatewayUrl: 'http://gateway.example',
          redirectUri: 'http://127.0.0.1:8765/callback',
        });
        console.log(JSON.stringify({ url, called: calls[0] }));
    """)

    payload = json.loads(output)
    assert payload["url"].startswith("https://open.feishu.cn/")
    assert payload["called"] == (
        "http://gateway.example/auth/feishu/authorize-url?"
        "redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Fcallback"
    )


def test_auth_flow_uses_gateway_hosted_login_session(tmp_path):
    token_path = tmp_path / "token.json"
    output = run_node(f"""
        const calls = [];
        const warnings = [];
        process.env.PARQUET_DISABLE_BROWSER_OPEN = '1';
        console.error = (message) => warnings.push(message);
        globalThis.fetch = async (url, options = {{}}) => {{
          calls.push({{ url: String(url), method: options.method || 'GET' }});
          if (String(url).endsWith('/auth/feishu/login-session')) {{
            return {{
              ok: true,
              status: 200,
              statusText: 'OK',
              text: async () => JSON.stringify({{
                session_id: 'login-session-1',
                auth_url: 'https://accounts.feishu.cn/open-apis/authen/v1/authorize?state=login-session-1',
                redirect_uri: 'http://gateway.example/auth/feishu/callback',
                expires_in: 600,
              }}),
            }};
          }}
          if (String(url).endsWith('/auth/feishu/login-session/login-session-1')) {{
            return {{
              ok: true,
              status: 200,
              statusText: 'OK',
              text: async () => JSON.stringify({{
                status: 'complete',
                access_token: 'gateway-token',
                token_type: 'bearer',
                expires_in: 3600,
              }}),
            }};
          }}
          throw new Error('unexpected fetch ' + String(url));
        }};
        const auth = await import('./auth-flow.js');
        const payload = await auth.loginWithFeishu({{
          gatewayUrl: 'http://gateway.example',
          savePath: {json.dumps(str(token_path))},
          pollIntervalMs: 1,
        }});
        const saved = await auth.readSavedGatewayToken({json.dumps(str(token_path))});
        console.log(JSON.stringify({{ payload, saved, calls, warnings }}));
    """)

    payload = json.loads(output)
    assert payload["payload"]["access_token"] == "gateway-token"
    assert payload["saved"] == "gateway-token"
    assert payload["calls"] == [
        {"url": "http://gateway.example/auth/feishu/login-session", "method": "POST"},
        {"url": "http://gateway.example/auth/feishu/login-session/login-session-1", "method": "GET"},
    ]
    assert any("copy this authorization URL" in warning for warning in payload["warnings"])


def test_gateway_hosted_login_error_includes_unmapped_user_details():
    output = run_node("""
        process.env.PARQUET_DISABLE_BROWSER_OPEN = '1';
        globalThis.fetch = async (url, options = {}) => {
          if (String(url).endsWith('/auth/feishu/login-session')) {
            return {
              ok: true,
              status: 200,
              statusText: 'OK',
              text: async () => JSON.stringify({
                session_id: 'login-session-1',
                auth_url: 'https://accounts.feishu.cn/open-apis/authen/v1/authorize?state=login-session-1',
                redirect_uri: 'http://gateway.example/auth/feishu/callback',
                expires_in: 600,
              }),
            };
          }
          if (String(url).endsWith('/auth/feishu/login-session/login-session-1')) {
            return {
              ok: true,
              status: 200,
              statusText: 'OK',
              text: async () => JSON.stringify({
                status: 'error',
                message: 'feishu user is not mapped to gateway permissions',
                details: { name: 'Alice Zhang', open_id: 'ou_alice' },
              }),
            };
          }
          throw new Error('unexpected fetch ' + String(url));
        };
        const auth = await import('./auth-flow.js');
        try {
          await auth.loginWithGatewaySession({
            gatewayUrl: 'http://gateway.example',
            pollIntervalMs: 1,
          });
        } catch (err) {
          console.log(err.message);
        }
    """)

    assert "feishu user is not mapped to gateway permissions" in output
    assert "Alice Zhang" in output
    assert "ou_alice" in output
    assert "email" not in output


def test_gateway_request_sends_client_version_and_warns_on_outdated_response():
    output = run_node("""
        const calls = [];
        const warnings = [];
        process.env.PARQUET_GATEWAY_URL = 'http://gateway.example';
        process.env.PARQUET_GATEWAY_TOKEN = 'token';
        console.error = (message) => warnings.push(message);
        globalThis.fetch = async (url, options) => {
          calls.push({
            url: String(url),
            version: options.headers['X-Parquet-Client-Version'],
          });
          return {
            ok: true,
            status: 200,
            statusText: 'OK',
            headers: {
              get: (name) => ({
                'X-Parquet-Client-Version-Status': 'outdated',
                'X-Parquet-Client-Latest-Version': '0.2.0',
                'X-Parquet-Client-Download-Url': '/downloads/parquet-query-gateway-client.zip',
                'X-Parquet-Client-Guide-Url': '/client-installation-guide.md',
              }[name] || null),
            },
            text: async () => JSON.stringify({ status: 'ok' }),
          };
        };
        const client = await import('./gateway-client.js');
        const payload = await client.gatewayRequest('/health', { auth: false });
        console.log(JSON.stringify({ payload, calls, warnings }));
    """)

    payload = json.loads(output)
    assert payload["payload"] == {"status": "ok"}
    assert payload["calls"][0] == {
        "url": "http://gateway.example/health",
        "version": "0.1.4",
    }
    assert payload["warnings"] == [
        "Parquet Gateway client 0.1.4 is older than server latest 0.2.0. Update: http://gateway.example/downloads/parquet-query-gateway-client.zip (guide: http://gateway.example/client-installation-guide.md)"
    ]


def test_windows_browser_open_avoids_cmd_ampersand_truncation():
    source = open("auth-flow.js", encoding="utf-8").read()

    assert "Start-Process" in source
    assert "-FilePath" in source
    assert "-LiteralPath" not in source
    assert "'cmd'" not in source
    assert "'/c', 'start'" not in source


def test_login_prints_authorization_url_as_fallback():
    source = open("auth-flow.js", encoding="utf-8").read()

    assert "copy this authorization URL into your browser" in source
    assert "the browser should return to" in source
    assert "opencli parquet login \"<code>\"" in source
    assert "console.error" in source
