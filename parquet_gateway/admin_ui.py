from __future__ import annotations


ADMIN_CONFIG_UI_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Parquet Gateway Config</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #64717f;
      --line: #d9e0e8;
      --blue: #155dfc;
      --green: #137a41;
      --red: #ba1a1a;
      --yellow: #8a5a00;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--ink); }
    header {
      height: 56px; display: flex; align-items: center; gap: 16px; padding: 0 18px;
      border-bottom: 1px solid var(--line); background: var(--panel); position: sticky; top: 0; z-index: 2;
    }
    h1 { font-size: 17px; margin: 0; font-weight: 700; }
    .token { flex: 1; display: flex; align-items: center; gap: 8px; min-width: 240px; }
    input, textarea, select {
      border: 1px solid var(--line); border-radius: 6px; background: white; color: var(--ink);
      font: inherit; padding: 8px 10px; min-width: 0;
    }
    .token input { width: 100%; }
    button {
      border: 1px solid var(--line); border-radius: 6px; background: white; color: var(--ink);
      font: inherit; padding: 8px 11px; cursor: pointer; white-space: nowrap;
    }
    button.primary { background: var(--blue); border-color: var(--blue); color: white; }
    button.danger { color: var(--red); }
    main { display: grid; grid-template-columns: minmax(380px, 46%) 1fr; gap: 14px; padding: 14px; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; min-height: calc(100vh - 84px); overflow: hidden; }
    .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px; border-bottom: 1px solid var(--line); }
    .panel-title { font-weight: 700; font-size: 14px; }
    .yaml { width: 100%; min-height: calc(100vh - 144px); border: 0; border-radius: 0; resize: vertical; font: 13px/1.45 ui-monospace, SFMono-Regular, Consolas, monospace; padding: 12px; }
    .tabs { display: flex; gap: 6px; padding: 10px 12px 0; }
    .tab { padding: 7px 10px; border: 1px solid var(--line); border-bottom: 0; border-radius: 6px 6px 0 0; color: var(--muted); }
    .tab.active { color: var(--ink); background: #eef3ff; border-color: #b8c9ff; }
    .view { display: none; padding: 12px; }
    .view.active { display: block; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    label { display: grid; gap: 5px; color: var(--muted); font-size: 12px; }
    label span { color: var(--muted); }
    label input, label textarea { width: 100%; color: var(--ink); }
    .row { display: flex; align-items: center; gap: 8px; }
    .row > * { flex: 1; }
    .card { border: 1px solid var(--line); border-radius: 8px; padding: 12px; margin-bottom: 10px; background: white; }
    .card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
    .card-title { font-weight: 700; font-size: 14px; overflow-wrap: anywhere; }
    .muted { color: var(--muted); font-size: 12px; }
    .status { font-size: 13px; min-width: 210px; color: var(--muted); }
    .status.ok { color: var(--green); }
    .status.err { color: var(--red); }
    .pill { display: inline-flex; align-items: center; padding: 2px 7px; border: 1px solid var(--line); border-radius: 999px; font-size: 12px; color: var(--muted); margin: 2px; }
    .toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .role-dropdown { position: relative; width: 100%; }
    .role-dropdown-toggle {
      width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 8px;
      text-align: left; min-height: 36px; color: var(--ink);
    }
    .role-dropdown-toggle::after { content: "v"; color: var(--muted); font-size: 11px; }
    .role-dropdown-menu {
      display: none; position: absolute; z-index: 5; left: 0; right: 0; top: calc(100% + 4px);
      max-height: 220px; overflow: auto; padding: 6px; border: 1px solid var(--line);
      border-radius: 6px; background: white; box-shadow: 0 10px 24px rgb(23 32 42 / 12%);
    }
    .role-dropdown.open .role-dropdown-menu { display: grid; gap: 2px; }
    .role-option {
      display: flex; align-items: center; gap: 8px; padding: 6px 7px; border-radius: 5px;
      color: var(--ink); font-size: 13px; cursor: pointer;
    }
    .role-option:hover { background: #f2f5f9; }
    .role-option input { width: auto; }
    .hidden { display: none; }
    @media (max-width: 980px) {
      header { height: auto; flex-wrap: wrap; padding: 12px; }
      main { grid-template-columns: 1fr; }
      .panel { min-height: auto; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Parquet Gateway Config</h1>
    <div class="token">
      <input id="token" type="password" autocomplete="off" placeholder="Admin bearer token" />
      <button id="load">加载</button>
    </div>
    <div id="status" class="status">未加载</div>
  </header>
  <main>
    <section class="panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">YAML</div>
          <div id="path" class="muted"></div>
        </div>
        <div class="toolbar">
          <button id="copy">复制</button>
          <button id="save" class="primary">保存</button>
        </div>
      </div>
      <textarea id="yaml" class="yaml" spellcheck="false"></textarea>
    </section>
    <section class="panel">
      <div class="tabs">
        <button class="tab active" data-tab="feishu">飞书用户</button>
        <button class="tab" data-tab="datasets">数据集</button>
        <button class="tab" data-tab="settings">基础配置</button>
      </div>
      <div id="feishu" class="view active">
        <div class="card">
          <div class="grid">
            <label><span>App ID</span><input id="feishu-app-id" /></label>
            <label><span>Redirect URI</span><input id="feishu-redirect-uri" /></label>
            <label><span>Enabled</span><select id="feishu-enabled"><option value="true">true</option><option value="false">false</option></select></label>
            <label><span>App Secret</span><input value="********" disabled /></label>
          </div>
        </div>
        <div class="toolbar" style="margin-bottom:10px">
          <button id="add-user">新增用户</button>
          <button id="sync-users">同步到 YAML</button>
        </div>
        <div id="users"></div>
      </div>
      <div id="datasets" class="view">
        <div class="toolbar" style="margin-bottom:10px">
          <button id="discover-datasets">扫描 Parquet 数据表</button>
          <button id="sync-datasets">同步字段权限到 YAML</button>
        </div>
        <div id="discovered-datasets"></div>
        <div id="dataset-list"></div>
      </div>
      <div id="settings" class="view">
        <div class="card">
          <div class="grid">
            <label><span>data_root</span><input id="data-root" /></label>
            <label><span>max_limit</span><input id="max-limit" type="number" min="1" /></label>
            <label><span>default_limit</span><input id="default-limit" type="number" min="1" /></label>
            <label><span>query_timeout_seconds</span><input id="timeout" type="number" min="1" /></label>
          </div>
          <div class="toolbar" style="margin-top:10px"><button id="sync-settings">同步到 YAML</button></div>
        </div>
      </div>
    </section>
  </main>
  <template id="user-template">
    <div class="card user-card">
      <div class="card-head">
        <div class="card-title user-title">用户</div>
        <button class="danger remove-user">删除</button>
      </div>
      <div class="grid">
        <label><span>name</span><input class="user-name" placeholder="飞书姓名" /></label>
        <label><span>open_id（可选）</span><input class="user-open-id" placeholder="管理员可后续补充" /></label>
        <label><span>id</span><input class="user-id" placeholder="内部用户 ID" /></label>
        <label><span>roles</span><div class="user-roles"></div></label>
      </div>
      <div class="muted" style="margin-top:10px">attributes</div>
      <div class="user-attribute-fields grid"></div>
      <details style="margin-top:10px">
        <summary class="muted">高级 JSON</summary>
        <textarea class="user-attributes" rows="3">{}</textarea>
      </details>
    </div>
  </template>
  <script>
    let config = null;
    const DEFAULT_ROLES = ["analyst", "admin", "finance", "operations", "promotion", "warehouse", "hr"];
    const ROLE_LABELS = {
      analyst: "分析师",
      admin: "管理员",
      finance: "财务",
      operations: "运营",
      promotion: "推广",
      warehouse: "仓储",
      hr: "人事",
    };
    const $ = (id) => document.getElementById(id);
    const token = () => $("token").value.trim().replace(/^Bearer\s+/i, "").replace(/^["']|["']$/g, "").trim();
    const setStatus = (text, cls = "") => { $("status").className = "status " + cls; $("status").textContent = text; };
    const authHeaders = () => token() ? { Authorization: "Bearer " + token() } : {};
    const splitList = (value) => value.split(",").map((v) => v.trim()).filter(Boolean);
    const dump = (obj) => jsyamlDump(obj);

    document.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".tab,.view").forEach((el) => el.classList.remove("active"));
        tab.classList.add("active");
        $(tab.dataset.tab).classList.add("active");
      });
    });

    $("load").addEventListener("click", loadConfig);
    $("save").addEventListener("click", saveConfig);
    $("copy").addEventListener("click", async () => { await navigator.clipboard.writeText($("yaml").value); setStatus("已复制 YAML", "ok"); });
    $("add-user").addEventListener("click", () => addUserCard({ roles: ["analyst"], attributes: {} }));
    $("sync-users").addEventListener("click", () => { syncUsersFromForm(); renderYaml(); setStatus("用户已同步到 YAML", "ok"); });
    $("sync-settings").addEventListener("click", () => { syncSettingsFromForm(); renderYaml(); setStatus("基础配置已同步到 YAML", "ok"); });
    $("discover-datasets").addEventListener("click", discoverDatasets);
    $("sync-datasets").addEventListener("click", () => { syncDatasetsFromForm(); renderYaml(); setStatus("字段权限已同步到 YAML", "ok"); });
    $("feishu-app-id").addEventListener("input", syncFeishuForm);
    $("feishu-redirect-uri").addEventListener("input", syncFeishuForm);
    $("feishu-enabled").addEventListener("change", syncFeishuForm);

    async function loadConfig() {
      if (!token()) { setStatus("请输入 admin token", "err"); return; }
      setStatus("加载中...");
      const res = await fetch("/admin/config", { headers: authHeaders() });
      const body = await res.json();
      if (!res.ok) { setStatus(body.error?.message || "加载失败", "err"); return; }
      config = body.config;
      $("path").textContent = body.path;
      renderAll();
      setStatus("已加载", "ok");
    }

    async function saveConfig() {
      if (!token()) { setStatus("请输入 admin token", "err"); return; }
      setStatus("保存中...");
      const res = await fetch("/admin/config", {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ yaml: $("yaml").value }),
      });
      const body = await res.json();
      if (!res.ok) { setStatus(body.error?.message || "保存失败", "err"); return; }
      setStatus("已保存，备份 " + body.backup_path, "ok");
      await loadConfig();
    }

    function renderAll() {
      renderFeishu();
      renderUsers();
      renderDatasets();
      renderSettings();
      renderYaml();
    }

    function renderFeishu() {
      const feishu = config.auth?.feishu || {};
      $("feishu-app-id").value = feishu.app_id || "";
      $("feishu-redirect-uri").value = feishu.redirect_uri || "";
      $("feishu-enabled").value = String(Boolean(feishu.enabled));
    }

    function renderUsers() {
      $("users").innerHTML = "";
      (config.auth?.feishu_users || []).forEach(addUserCard);
    }

    function addUserCard(user) {
      const node = $("user-template").content.firstElementChild.cloneNode(true);
      node.querySelector(".user-open-id").value = user.open_id || "";
      node.querySelector(".user-name").value = user.name || "";
      node.querySelector(".user-id").value = user.id || "";
      renderRoleDropdown(node.querySelector(".user-roles"), user.roles || []);
      renderAttributeFields(node.querySelector(".user-attribute-fields"), user.attributes || {});
      node.querySelector(".user-attributes").value = JSON.stringify(user.attributes || {}, null, 2);
      const updateTitle = () => { node.querySelector(".user-title").textContent = node.querySelector(".user-id").value || node.querySelector(".user-name").value || node.querySelector(".user-open-id").value || "新用户"; };
      node.querySelectorAll("input,textarea").forEach((el) => el.addEventListener("input", updateTitle));
      node.querySelector(".remove-user").addEventListener("click", () => node.remove());
      updateTitle();
      $("users").appendChild(node);
    }

    function knownRoles() {
      const roles = new Set(DEFAULT_ROLES);
      Object.values(config?.datasets || {}).forEach((dataset) => {
        (dataset.roles || []).forEach((role) => roles.add(role));
        Object.keys(dataset.columns || {}).forEach((role) => roles.add(role));
      });
      (config?.auth?.feishu_users || []).forEach((user) => (user.roles || []).forEach((role) => roles.add(role)));
      return Array.from(roles).sort((a, b) => a === "analyst" ? -1 : b === "analyst" ? 1 : a.localeCompare(b));
    }

    function renderRoleDropdown(container, selected) {
      const selectedSet = new Set(selected || []);
      container.innerHTML = `
        <div class="role-dropdown">
          <button type="button" class="role-dropdown-toggle"></button>
          <div class="role-dropdown-menu">
            ${knownRoles().map((role) => `
              <label class="role-option">
                <input type="checkbox" class="role-check" value="${escapeHtml(role)}" ${selectedSet.has(role) ? "checked" : ""} />
                <span>${escapeHtml(roleLabel(role))}</span>
              </label>
            `).join("")}
          </div>
        </div>
      `;
      const dropdown = container.querySelector(".role-dropdown");
      const toggle = container.querySelector(".role-dropdown-toggle");
      const update = () => {
        const labels = selectedRoles(container).map(roleLabel);
        toggle.textContent = labels.length ? labels.join(", ") : "选择角色";
      };
      toggle.addEventListener("click", () => dropdown.classList.toggle("open"));
      container.querySelectorAll(".role-check").forEach((input) => input.addEventListener("change", update));
      update();
    }

    function selectedRoles(container) {
      return Array.from(container.querySelectorAll(".role-check:checked")).map((input) => input.value);
    }

    function roleLabel(role) {
      return ROLE_LABELS[role] || role;
    }

    function knownAttributeKeys() {
      const keys = new Set();
      Object.values(config?.datasets || {}).forEach((dataset) => {
        const source = dataset.row_policy?.source || "";
        if (source.startsWith("attributes.")) keys.add(source.slice("attributes.".length));
      });
      (config?.auth?.feishu_users || []).forEach((user) => Object.keys(user.attributes || {}).forEach((key) => keys.add(key)));
      return Array.from(keys).sort();
    }

    function renderAttributeFields(container, attributes) {
      const keys = knownAttributeKeys();
      if (!keys.length) {
        container.innerHTML = '<div class="muted">当前数据集没有 row_policy，通常保持 {} 即可。</div>';
        return;
      }
      container.innerHTML = keys.map((key) => {
        const value = attributes?.[key];
        const text = Array.isArray(value) ? value.join(", ") : value == null ? "" : String(value);
        return `<label><span>${escapeHtml(key)}</span><input class="attribute-field" data-key="${escapeHtml(key)}" value="${escapeHtml(text)}" placeholder="多个值用逗号分隔" /></label>`;
      }).join("");
    }

    function syncFeishuForm() {
      if (!config) return;
      config.auth ||= {};
      config.auth.feishu ||= {};
      config.auth.feishu.enabled = $("feishu-enabled").value === "true";
      config.auth.feishu.app_id = $("feishu-app-id").value.trim();
      config.auth.feishu.redirect_uri = $("feishu-redirect-uri").value.trim();
      renderYaml();
    }

    function syncUsersFromForm() {
      config.auth ||= {};
      config.auth.feishu_users = Array.from(document.querySelectorAll(".user-card")).map((node) => {
        let attributes = {};
        try { attributes = JSON.parse(node.querySelector(".user-attributes").value || "{}"); } catch { attributes = {}; }
        node.querySelectorAll(".attribute-field").forEach((input) => {
          const values = splitList(input.value);
          if (values.length) attributes[input.dataset.key] = values;
          else delete attributes[input.dataset.key];
        });
        const user = {
          id: node.querySelector(".user-id").value.trim(),
          roles: selectedRoles(node.querySelector(".user-roles")),
          attributes,
        };
        const openId = node.querySelector(".user-open-id").value.trim();
        const name = node.querySelector(".user-name").value.trim();
        if (openId) user.open_id = openId;
        if (name) user.name = name;
        return user;
      });
    }

    function renderDatasets() {
      const wrap = $("dataset-list");
      wrap.innerHTML = "";
      Object.entries(config.datasets || {}).forEach(([id, dataset]) => {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
          <div class="card-head"><div><div class="card-title"></div><div class="muted dataset-path"></div></div></div>
          <div class="grid">
            <label><span>roles</span><div class="dataset-roles"></div></label>
            <label><span>description</span><input class="dataset-description" /></label>
          </div>
          <div class="muted" style="margin-top:10px">字段权限</div><div class="columns"></div>
        `;
        card.dataset.datasetId = id;
        card.querySelector(".card-title").textContent = id;
        card.querySelector(".dataset-path").textContent = dataset.path || "";
        renderRoleDropdown(card.querySelector(".dataset-roles"), dataset.roles || []);
        card.querySelector(".dataset-description").value = dataset.description || "";
        card.querySelector(".columns").innerHTML = Object.entries(dataset.columns || {}).map(([role, cols]) =>
          `<label style="margin-top:8px"><span>${escapeHtml(role)} columns</span><textarea class="dataset-columns" data-role="${escapeHtml(role)}" rows="3">${escapeHtml((cols || []).join(", "))}</textarea></label>`
        ).join("");
        wrap.appendChild(card);
      });
    }

    async function discoverDatasets() {
      if (!token()) { setStatus("请输入 admin token", "err"); return; }
      setStatus("扫描中...");
      const res = await fetch("/admin/config/discover-datasets", { headers: authHeaders() });
      const body = await res.json();
      if (!res.ok) { setStatus(body.error?.message || "扫描失败", "err"); return; }
      renderDiscoveredDatasets(body.datasets || []);
      setStatus(`发现 ${(body.datasets || []).length} 张数据表`, "ok");
    }

    function renderDiscoveredDatasets(datasets) {
      const wrap = $("discovered-datasets");
      wrap.innerHTML = "";
      datasets.forEach((dataset) => {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
          <div class="card-head">
            <div><div class="card-title"></div><div class="muted"></div></div>
            <button class="add-discovered"></button>
          </div>
          <div class="columns"></div>
        `;
        card.querySelector(".card-title").textContent = dataset.id;
        card.querySelector(".muted").textContent = `${dataset.path} · ${dataset.file_count} files`;
        const button = card.querySelector(".add-discovered");
        button.textContent = dataset.configured ? "已配置" : "添加到 YAML";
        button.disabled = Boolean(dataset.configured);
        button.addEventListener("click", () => addDiscoveredDataset(dataset));
        card.querySelector(".columns").innerHTML = (dataset.columns || []).map((col) => `<span class="pill">${escapeHtml(col)}</span>`).join("");
        wrap.appendChild(card);
      });
    }

    function addDiscoveredDataset(dataset) {
      config.datasets ||= {};
      config.datasets[dataset.id] = {
        description: dataset.description || dataset.id,
        path: dataset.path,
        roles: DEFAULT_ROLES,
        columns: Object.fromEntries(DEFAULT_ROLES.map((role) => [role, dataset.columns || []])),
      };
      renderDatasets();
      renderYaml();
      setStatus(`${dataset.id} 已添加到 YAML`, "ok");
    }

    function syncDatasetsFromForm() {
      document.querySelectorAll("#dataset-list .card").forEach((card) => {
        const id = card.dataset.datasetId;
        if (!id || !config.datasets?.[id]) return;
        const dataset = config.datasets[id];
        dataset.description = card.querySelector(".dataset-description").value.trim();
        dataset.roles = selectedRoles(card.querySelector(".dataset-roles"));
        dataset.columns = {};
        card.querySelectorAll(".dataset-columns").forEach((textarea) => {
          dataset.columns[textarea.dataset.role] = splitList(textarea.value);
        });
      });
    }

    function renderSettings() {
      const s = config.settings || {};
      $("data-root").value = s.data_root || "";
      $("max-limit").value = s.max_limit || "";
      $("default-limit").value = s.default_limit || "";
      $("timeout").value = s.query_timeout_seconds || "";
    }

    function syncSettingsFromForm() {
      config.settings ||= {};
      config.settings.data_root = $("data-root").value.trim();
      config.settings.max_limit = Number($("max-limit").value);
      config.settings.default_limit = Number($("default-limit").value);
      config.settings.query_timeout_seconds = Number($("timeout").value);
    }

    function renderYaml() {
      $("yaml").value = dump(config);
    }

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    }

    function jsyamlDump(obj, indent = 0) {
      if (Array.isArray(obj)) {
        if (!obj.length) return "[]";
        return obj.map((item) => " ".repeat(indent) + "- " + formatYamlValue(item, indent + 2)).join("\n");
      }
      if (obj && typeof obj === "object") {
        return Object.entries(obj).map(([key, value]) => {
          if (value && typeof value === "object") return " ".repeat(indent) + key + ":\n" + jsyamlDump(value, indent + 2);
          return " ".repeat(indent) + key + ": " + formatScalar(value);
        }).join("\n");
      }
      return formatScalar(obj);
    }

    function formatYamlValue(value, indent) {
      if (value && typeof value === "object") {
        const rendered = jsyamlDump(value, indent);
        return rendered.includes("\n") ? "\n" + rendered : rendered;
      }
      return formatScalar(value);
    }

    function formatScalar(value) {
      if (value === null || value === undefined) return "";
      if (typeof value === "boolean" || typeof value === "number") return String(value);
      const text = String(value);
      if (!text || /[:#\[\]{},&*?|>'"%@`]/.test(text) || /^\s|\s$/.test(text)) return JSON.stringify(text);
      return text;
    }
  </script>
</body>
</html>"""
