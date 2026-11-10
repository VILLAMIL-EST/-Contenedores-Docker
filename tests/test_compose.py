"""Validate both real Compose models, not just file existence."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def model(*flags):
    result = subprocess.run(["docker", "compose", *flags, "config", "--format", "json"], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)["services"]


class ComposeTests(unittest.TestCase):
    def test_two_servers_and_matching_nginx(self):
        services = model("-f", "compose.yaml")
        self.assertEqual(set(services), {"servidor1", "servidor2", "balanceador"})
        self.assertTrue(services["balanceador"]["volumes"][0]["source"].endswith("/nginx/nginx.conf"))
        conf = (ROOT / "nginx/nginx.conf").read_text()
        self.assertIn("server servidor1:8000;", conf)
        self.assertIn("server servidor2:8000;", conf)
        self.assertNotIn("server servidor3:8000;", conf)

    def test_three_servers_and_matching_nginx(self):
        services = model("--profile", "tres", "-f", "compose.yaml", "-f", "compose.tres.yaml")
        self.assertEqual(set(services), {"servidor1", "servidor2", "servidor3", "balanceador"})
        self.assertTrue(services["balanceador"]["volumes"][0]["source"].endswith("/nginx/nginx.tres.conf"))
        conf = (ROOT / "nginx/nginx.tres.conf").read_text()
        for i in (1, 2, 3):
            self.assertIn(f"server servidor{i}:8000;", conf)

    def test_nginx_retries_another_backend_before_client_timeout(self):
        for name in ("nginx.conf", "nginx.tres.conf"):
            with self.subTest(name=name):
                conf = (ROOT / "nginx" / name).read_text()
                self.assertIn("proxy_connect_timeout 1s;", conf)
                self.assertIn("proxy_next_upstream error timeout", conf)


if __name__ == "__main__":
    unittest.main()
