import hashlib
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINUX_SHA = "5ac3990374900362acad4f8b847e22a48d8aafa7ab9de9943254f215e3e79275"


class WrapperTests(unittest.TestCase):
    def test_linux_wrapper_unchanged_and_parses(self):
        script = ROOT / "iniciar.sh"
        self.assertTrue(script.exists())
        text = script.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.assertEqual(digest, LINUX_SHA, "iniciar.sh no debe alterarse en el arreglo Windows")
        subprocess.run(["bash", "-n", str(script)], check=True)
        self.assertIn('exec "$VENV/bin/python" "$ROOT/launcher.py" "$@"', text)

    def test_windows_cmd_entry_bypasses_execution_policy(self):
        script = ROOT / "iniciar.cmd"
        self.assertTrue(script.exists())
        text = script.read_text(encoding="utf-8")
        self.assertIn('cd /d "%~dp0"', text)
        self.assertIn("ExecutionPolicy Bypass", text)
        self.assertIn(r"scripts\windows\preparar.ps1", text)
        self.assertIn("--servidores", text)
        self.assertNotIn("H:\\tensors", text)
        self.assertNotIn("C:\\home\\raven", text)

    def test_activar_cmd_aliases_iniciar_cmd(self):
        script = ROOT / "activar.cmd"
        self.assertTrue(script.exists())
        text = script.read_text(encoding="utf-8")
        self.assertIn("iniciar.cmd", text)
        self.assertIn('cd /d "%~dp0"', text)

    def test_windows_bootstrap_refreshes_path_and_handles_wsl(self):
        script = ROOT / "scripts" / "windows" / "preparar.ps1"
        self.assertTrue(script.exists())
        text = script.read_text(encoding="utf-8")
        self.assertIn("Update-SessionPath", text)
        self.assertIn("GetEnvironmentVariable('Path'", text)
        self.assertIn("DockerDesktop", text)
        self.assertIn("wsl --install --no-distribution", text)
        self.assertIn("Docker.DockerDesktop", text)
        self.assertIn("launcher.py", text)
        self.assertIn("requirements-cli.txt", text)
        self.assertNotIn("Set-ExecutionPolicy RemoteSigned", text)

    def test_windows_ps1_delegates_to_iniciar_cmd(self):
        script = ROOT / "iniciar.ps1"
        self.assertTrue(script.exists())
        text = script.read_text(encoding="utf-8")
        self.assertIn("$PSScriptRoot", text)
        self.assertIn("iniciar.cmd", text)
        self.assertIn("servidores", text)
        self.assertNotIn("C:\\home\\raven", text)


if __name__ == "__main__":
    unittest.main()
