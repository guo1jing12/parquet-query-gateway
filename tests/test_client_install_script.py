from pathlib import Path


def test_windows_client_installer_updates_existing_plugin_on_native_command_failure():
    script = Path("scripts/client-install.ps1").read_text(encoding="utf-8")

    assert "opencli.cmd plugin install $pluginPath" in script
    assert "if ($LASTEXITCODE -ne 0)" in script
    assert "opencli.cmd plugin update parquet" in script


def test_client_package_includes_shared_auth_flow():
    script = Path("scripts/package-client.ps1").read_text(encoding="utf-8")

    assert '"auth-flow.js"' in script
