import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from backend.config.vault import DEFAULT_VAULT_ROOT, VaultConfigurationError, VaultSettings


class VaultSettingsTests(unittest.TestCase):
    def test_unset_uses_backward_compatible_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = VaultSettings.from_environment()
        self.assertEqual(settings.root, DEFAULT_VAULT_ROOT)
        self.assertFalse(settings.explicitly_configured)

    def test_local_path_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"KM_VAULT_ROOT": directory}, clear=True
        ):
            settings = VaultSettings.from_environment()
            self.assertEqual(settings.root, Path(directory).resolve())
            self.assertEqual(settings.require_readable(), settings.root)
            self.assertEqual(settings.require_writable(), settings.root)

    @unittest.skipUnless(os.name == "nt", "UNC path behavior is Windows-specific")
    def test_unc_path_is_preserved(self) -> None:
        unc = r"\\10.28.255.19\KM\Vault"
        with patch.dict(os.environ, {"KM_VAULT_ROOT": unc}, clear=True):
            settings = VaultSettings.from_environment()
        self.assertEqual(str(settings.root), unc)

    def test_configured_missing_path_fails_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / "missing")
            with patch.dict(os.environ, {"KM_VAULT_ROOT": missing}, clear=True):
                settings = VaultSettings.from_environment()
                with self.assertRaisesRegex(VaultConfigurationError, "unavailable"):
                    settings.require_readable()
            self.assertNotEqual(settings.root, DEFAULT_VAULT_ROOT)

    def test_read_and_write_failures_are_clear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = VaultSettings(Path(directory), explicitly_configured=True)
            with patch("backend.config.vault.os.scandir", side_effect=PermissionError):
                with self.assertRaisesRegex(VaultConfigurationError, "not readable"):
                    settings.require_readable()
            with patch("backend.config.vault.tempfile.mkstemp", side_effect=PermissionError):
                with self.assertRaisesRegex(VaultConfigurationError, "not writable"):
                    settings.require_writable()


class _MismatchHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({"health": "ok", "vaultRoot": r"C:\different\vault"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class NodeVaultConsistencyTests(unittest.TestCase):
    def test_node_rejects_fastapi_vault_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = ThreadingHTTPServer(("127.0.0.1", 0), _MismatchHealthHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                node_port = probe.getsockname()[1]
            environment = os.environ.copy()
            environment.update({
                "KM_VAULT_ROOT": directory,
                "FASTAPI_TRAINING_URL": f"http://127.0.0.1:{server.server_port}",
                "PORT": str(node_port),
            })
            try:
                result = subprocess.run(
                    ["node", "server.js"], cwd=Path(__file__).resolve().parents[1],
                    env=environment, capture_output=True, text=True, timeout=10,
                )
            finally:
                server.shutdown()
                server.server_close()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Vault root mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
