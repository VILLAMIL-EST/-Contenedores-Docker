import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import interactive


class InteractiveTests(unittest.TestCase):
    def setUp(self):
        self.compose = ["docker", "compose", "-p", "taller-test"]
        self.run = Mock()
        self.fetch = Mock()

    def test_parse_commands_and_bound_server_ids(self):
        for command in ("estado", "informe", "ayuda", "salir"):
            self.assertEqual(interactive.parse_command(command, 2), (command, None))
        self.assertEqual(interactive.parse_command("probar", 2), ("probar", 10))
        self.assertEqual(interactive.parse_command("probar 5", 2), ("probar", 5))
        self.assertEqual(interactive.parse_command(" probar 1 ", 3), ("probar", 1))
        self.assertEqual(interactive.parse_command(" detener 2 ", 2), ("detener", 2))
        self.assertEqual(interactive.parse_command("iniciar 3", 3), ("iniciar", 3))
        for command in ("detener 3", "iniciar 0", "detener x", "iniciar", "desconocido", "probar 0", "probar -1", "probar x", "probar 2 3"):
            with self.subTest(command=command), self.assertRaises(ValueError):
                interactive.parse_command(command, 2)

    def test_probe_round_respects_requested_count(self):
        self.fetch.side_effect = [{"mensaje": "Hola desde el Servidor 1"}] * 3
        records = interactive.probe_round(2, self.fetch, count=3)
        self.assertEqual(len(records), 3)
        self.assertEqual([r["intento"] for r in records], [1, 2, 3])
        self.assertEqual(self.fetch.call_count, 3)

    def test_stopped_container_is_disconnected_without_exec(self):
        rows = [{"Service": "servidor1", "State": "exited"}, {"Service": "servidor2", "State": "running"}]
        self.run.return_value = subprocess.CompletedProcess([], 0, "\n".join(map(json.dumps, rows)), "")
        state = interactive.server_status(1, self.compose, self.run)
        self.assertEqual(state["docker"], "exited")
        self.assertEqual(state["http"], "desconectado")
        self.assertEqual(self.run.call_count, 1)

    def test_running_container_requires_its_own_health_response(self):
        self.run.side_effect = [
            subprocess.CompletedProcess([], 0, json.dumps({"Service": "servidor1", "State": "running"}), ""),
            subprocess.CompletedProcess([], 0, '{"estado":"OK","servidor":"Servidor 1"}', ""),
        ]
        state = interactive.server_status(1, self.compose, self.run)
        self.assertEqual(state["http"], "conectado")
        self.assertIn("exec", self.run.call_args.args[0])
        self.assertIn("servidor1", self.run.call_args.args[0])

    def test_running_container_with_failed_health_is_not_connected(self):
        self.run.side_effect = [
            subprocess.CompletedProcess([], 0, json.dumps({"Service": "servidor1", "State": "running"}), ""),
            subprocess.CompletedProcess([], 1, "", "connection refused"),
        ]
        state = interactive.server_status(1, self.compose, self.run)
        self.assertEqual(state["docker"], "running")
        self.assertEqual(state["http"], "desconectado")
        self.assertIn("connection refused", state["detalle"])

    def test_control_affects_only_selected_server_and_verifies_state(self):
        status = Mock(return_value={"docker": "exited", "http": "desconectado"})
        self.run.return_value = subprocess.CompletedProcess([], 0, "", "")
        result = interactive.control_server("detener", 2, self.compose, self.run, status)
        self.assertEqual(self.run.call_args.args[0][-2:], ["stop", "servidor2"])
        self.assertEqual(result["docker"], "exited")
        status.assert_called_once()

    def test_start_waits_for_http_health_after_container_runs(self):
        status = Mock(side_effect=[
            {"docker": "running", "http": "desconectado", "detalle": "arrancando"},
            {"docker": "running", "http": "conectado", "detalle": ""},
        ])
        self.run.return_value = subprocess.CompletedProcess([], 0, "", "")
        with unittest.mock.patch("interactive.time.sleep"):
            observed = interactive.control_server("iniciar", 1, self.compose, self.run, status)
        self.assertEqual(observed["http"], "conectado")
        self.assertEqual(status.call_count, 2)

    def test_probe_round_records_all_ten_even_with_errors(self):
        self.fetch.side_effect = [ConnectionError("caído")] + [{"mensaje": "Hola desde el Servidor 2"}] * 9
        records = interactive.probe_round(2, self.fetch)
        self.assertEqual(len(records), 10)
        self.assertEqual(records[0]["servidor"], "")
        self.assertIn("caído", records[0]["error"])
        self.assertEqual([r["servidor"] for r in records[1:]], ["Servidor 2"] * 9)
        self.assertTrue(all("fecha" in r and "duracion_ms" in r for r in records))
        self.assertEqual(self.fetch.call_count, 10)

    def test_report_contains_observed_events_and_csv_rows(self):
        session = interactive.Session(3)
        session.add("detener", servidor="Servidor 1", docker="exited", http="desconectado")
        session.add("solicitud", fecha="2026-11-09T10:00:00-05:00", etapa="manual 1", intento=1, servidor="", error="502", duracion_ms=12)
        with tempfile.TemporaryDirectory() as directory:
            markdown, csv_file = interactive.export_report(session, Path(directory))
            self.assertIn("detener", markdown.read_text(encoding="utf-8"))
            self.assertIn("502", markdown.read_text(encoding="utf-8"))
            self.assertIn("502", csv_file.read_text(encoding="utf-8"))
            self.assertIn("2026-11-09T10:00:00-05:00", csv_file.read_text(encoding="utf-8"))
            self.assertIn("manual 1", csv_file.read_text(encoding="utf-8"))
            self.assertIn("modo_servidores,inicio_sesion", csv_file.read_text(encoding="utf-8"))
            self.assertIn(",3," + session.started_at + ",", csv_file.read_text(encoding="utf-8"))
            self.assertEqual(csv_file.read_text(encoding="utf-8").count("\n"), 2)


if __name__ == "__main__":
    unittest.main()
