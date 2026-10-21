import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import app


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class AssistantHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.CodingAssistantHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post_json(self, payload):
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def test_generate_calls_local_model_and_returns_answer(self):
        model_response = FakeResponse({"message": {"content": "print('hola')"}})
        with patch("app.urlopen", return_value=model_response) as call:
            status, payload = self.post_json(
                {"mode": "generate", "language": "Python", "prompt": "Saluda"}
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["response"], "print('hola')")
        outbound = call.call_args.args[0]
        self.assertEqual(outbound.full_url, f"{app.OLLAMA_URL}/api/chat")
        body = json.loads(outbound.data)
        self.assertEqual(body["model"], app.OLLAMA_MODEL)
        self.assertFalse(body["stream"])

    def test_fix_sends_user_code_to_local_model(self):
        model_response = FakeResponse({"message": {"content": "print('hola')"}})
        with patch("app.urlopen", return_value=model_response) as call:
            status, _ = self.post_json(
                {
                    "mode": "fix",
                    "language": "Python",
                    "prompt": "Corrige el error",
                    "code": "print('hola'",
                }
            )

        self.assertEqual(status, 200)
        task = json.loads(call.call_args.args[0].data)["messages"][1]["content"]
        self.assertIn("Corrige el error", task)
        self.assertIn("print('hola'", task)

    def test_fix_requires_code(self):
        status, payload = self.post_json(
            {"mode": "fix", "language": "Python", "prompt": "Corrige", "code": " "}
        )
        self.assertEqual(status, 400)
        self.assertIn("Pega el código", payload["error"])

    def test_rejects_invalid_language(self):
        status, payload = self.post_json(
            {"mode": "generate", "language": "unknown", "prompt": "Crea algo"}
        )
        self.assertEqual(status, 400)
        self.assertIn("lenguaje", payload["error"])

    def test_rejects_non_string_mode(self):
        status, payload = self.post_json(
            {"mode": [], "language": "Python", "prompt": "Crea algo"}
        )
        self.assertEqual(status, 400)
        self.assertIn("generar o corregir", payload["error"])

    def test_reports_empty_model_response(self):
        with patch("app.urlopen", return_value=FakeResponse([])):
            status, payload = self.post_json(
                {"mode": "generate", "language": "Python", "prompt": "Saluda"}
            )
        self.assertEqual(status, 502)
        self.assertIn("vacía", payload["error"])

    def test_reports_local_model_connection_error(self):
        with patch("app.urlopen", side_effect=URLError("offline")):
            status, payload = self.post_json(
                {"mode": "generate", "language": "Python", "prompt": "Saluda"}
            )
        self.assertEqual(status, 502)
        self.assertIn("Ollama", payload["error"])

    def test_serves_home_page(self):
        with urlopen(f"{self.base_url}/", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("lang=\"es\"", response.read().decode("utf-8"))
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_serves_javascript_and_stylesheet(self):
        for path, marker in (
            ("/static/app.js", "assistant-form"),
            ("/static/styles.css", ".workspace"),
        ):
            with urlopen(f"{self.base_url}{path}", timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(marker, response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
