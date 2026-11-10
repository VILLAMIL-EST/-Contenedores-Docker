import subprocess
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import launcher


class LauncherTests(unittest.TestCase):
    def test_local_health_bypasses_environment_proxy(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"estado":"OK"}')

            def log_message(self, *args):
                pass

        with HTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1", "HTTP_PROXY": "http://127.0.0.1:1", "no_proxy": "", "NO_PROXY": ""}):
                    self.assertEqual(launcher.fetch_json(f"http://127.0.0.1:{server.server_port}/"), {"estado": "OK"})
            finally:
                server.shutdown()
                thread.join()

    def test_command_selects_profile_and_override_only_for_three(self):
        self.assertEqual(launcher.compose_command(2)[:4], ["docker", "compose", "-f", "compose.yaml"])
        self.assertNotIn("--profile", launcher.compose_command(2))
        self.assertIn("--profile", launcher.compose_command(3))
        self.assertIn("compose.tres.yaml", launcher.compose_command(3))
        self.assertIn("-p", launcher.compose_command(2))
        self.assertEqual(launcher.compose_command(2)[launcher.compose_command(2).index("-p")+1], launcher.compose_command(3)[launcher.compose_command(3).index("-p")+1])
        with self.assertRaises(ValueError):
            launcher.compose_command(4)

    @patch("launcher.run_command")
    def test_existing_stack_is_rejected_without_down(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "abc123\n", "")
        with self.assertRaisesRegex(RuntimeError, "existentes"):
            launcher.launch(2)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn("down", run.call_args.args[0])

    @patch("launcher.wait_until_healthy")
    @patch("launcher.record_requests")
    @patch("launcher.run_command")
    def test_interrupt_cleans_up_own_stack(self, run, record, healthy):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        with patch("launcher.interactive.interactive_loop", side_effect=KeyboardInterrupt):
            launcher.launch(3)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertTrue(any(cmd[-1] == "down" for cmd in commands))
        self.assertTrue(any(cmd[-3:] == ["up", "-d", "--no-build"] for cmd in commands))
        healthy.assert_called_once_with(3)
        record.assert_called_once_with(3)

    @patch("launcher.run_command")
    def test_build_failure_does_not_down_foreign_resources(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, "", ""), subprocess.CompletedProcess([], 1, "", "build failed")]
        with self.assertRaisesRegex(RuntimeError, "build failed"):
            launcher.launch(2)
        self.assertEqual(run.call_count, 2)

    @patch("launcher.wait_until_healthy", side_effect=TimeoutError("salud agotada"))
    @patch("launcher.run_command")
    def test_health_failure_downs_started_stack(self, run, _healthy):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        with self.assertRaises(TimeoutError):
            launcher.launch(2)
        self.assertEqual(run.call_args.args[0][-1], "down")

    @patch("launcher.run_command")
    def test_partial_up_failure_still_downs_own_project(self, run):
        success = subprocess.CompletedProcess([], 0, "", "")
        failure = subprocess.CompletedProcess([], 1, "", "up failed")
        run.side_effect = [success, success, failure, success]
        with self.assertRaisesRegex(RuntimeError, "up failed"):
            launcher.launch(2)
        self.assertEqual(run.call_args.args[0][-1], "down")

    @patch("launcher.wait_until_healthy", side_effect=TimeoutError("salud agotada"))
    @patch("launcher.run_command")
    def test_down_failure_does_not_hide_health_failure(self, run, _healthy):
        success = subprocess.CompletedProcess([], 0, "", "")
        failure = subprocess.CompletedProcess([], 1, "", "down failed")
        run.side_effect = [success, success, success, failure]
        with self.assertRaisesRegex(TimeoutError, "salud agotada"):
            launcher.launch(2)
        self.assertEqual(run.call_args.args[0][-1], "down")

    @patch("launcher.fetch_json")
    def test_ten_requests_reach_expected_servers(self, fetch):
        fetch.side_effect = [{"mensaje": f"Hola desde el Servidor {(i % 3) + 1}"} for i in range(10)]
        responses = launcher.record_requests(3)
        self.assertEqual(len(responses), 10)
        self.assertEqual(set(responses), {"Servidor 1", "Servidor 2", "Servidor 3"})

    @patch("launcher.interactive.interactive_loop", side_effect=KeyboardInterrupt)
    @patch("launcher.wait_until_healthy")
    @patch("launcher.record_requests", return_value=["Servidor 1"] * 10)
    @patch("launcher.run_command")
    def test_launch_opens_interactive_console_and_preserves_cleanup(self, run, records, healthy, loop):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        launcher.launch(2)
        loop.assert_called_once()
        session = loop.call_args.args[-1]
        self.assertEqual(session.servers, 2)
        self.assertEqual(len([event for event in session.events if event["accion"] == "solicitud"]), 10)
        self.assertEqual(run.call_args.args[0][-1], "down")

    @patch("launcher.interactive.interactive_loop", return_value=None)
    @patch("launcher.wait_until_healthy")
    @patch("launcher.record_requests", return_value=["Servidor 1"] * 10)
    @patch("launcher.run_command")
    def test_eof_from_console_also_downs_own_stack(self, run, _records, _healthy, _loop):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        launcher.launch(2)
        self.assertEqual(run.call_args.args[0][-1], "down")

    @patch("launcher.interactive.interactive_loop", side_effect=SystemExit(129))
    @patch("launcher.wait_until_healthy")
    @patch("launcher.record_requests", return_value=["Servidor 1"] * 10)
    @patch("launcher.run_command")
    def test_terminal_hangup_also_downs_own_stack(self, run, _records, _healthy, _loop):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        with self.assertRaises(SystemExit):
            launcher.launch(2)
        self.assertEqual(run.call_args.args[0][-1], "down")

    @patch("launcher.run_command")
    def test_stop_project_downs_full_stack(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        launcher.stop_project()
        command = run.call_args.args[0]
        self.assertEqual(command[-1], "down")
        self.assertIn("--profile", command)
        self.assertIn("tres", command)


if __name__ == "__main__":
    unittest.main()
