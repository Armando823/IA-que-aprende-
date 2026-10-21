import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:3b")
APP_HOST = os.environ.get("APP_HOST", "127.0.0.1")
APP_PORT = int(os.environ.get("APP_PORT", "8000"))
MAX_REQUEST_BYTES = 256 * 1024
MAX_PROMPT_CHARS = 4000
MAX_CODE_CHARS = 16000
LANGUAGES = {
    "Python",
    "JavaScript",
    "TypeScript",
    "Java",
    "C#",
    "C++",
    "Go",
    "Rust",
    "Otro",
}
STATIC_FILES = {
    "/": (ROOT / "static" / "index.html", "text/html; charset=utf-8"),
    "/static/styles.css": (ROOT / "static" / "styles.css", "text/css; charset=utf-8"),
    "/static/app.js": (ROOT / "static" / "app.js", "text/javascript; charset=utf-8"),
}


def build_messages(mode, language, prompt, code=""):
    if mode == "fix":
        task = (
            f"Revisa y corrige este código en {language}. Solicitud del usuario: {prompt}\n\n"
            f"Código:\n```{language.lower()}\n{code}\n```\n\n"
            "Explica brevemente los cambios y devuelve el código completo corregido en un bloque "
            "de código. Si falta contexto, indica tus suposiciones. No afirmes que ejecutaste el código."
        )
    else:
        task = (
            f"Genera código en {language} para esta solicitud: {prompt}\n\n"
            "Explica brevemente la solución y presenta el código en un bloque de código. "
            "Si falta contexto, indica tus suposiciones."
        )
    return [
        {
            "role": "system",
            "content": (
                "Eres un asistente de programación útil y cuidadoso. Responde en español, "
                "prioriza código correcto y legible, y nunca digas que ejecutaste o probaste "
                "código si no lo hiciste."
            ),
        },
        {"role": "user", "content": task},
    ]


class CodingAssistantHandler(BaseHTTPRequestHandler):
    server_version = "LocalCodingAssistant/1.0"

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def do_GET(self):
        resource = STATIC_FILES.get(self.path)
        if resource is None:
            self.send_error(404, "No encontrado")
            return
        path, content_type = resource
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if self.path != "/api/generate":
            self.send_error(404, "No encontrado")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "La solicitud no tiene un tamaño válido."})
            return
        if content_length <= 0:
            self._send_json(400, {"error": "Envía una solicitud con contenido."})
            return
        if content_length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "La solicitud es demasiado grande."})
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "El cuerpo debe ser JSON válido."})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "El cuerpo debe ser un objeto JSON."})
            return

        mode = payload.get("mode")
        language = payload.get("language")
        prompt = payload.get("prompt")
        code = payload.get("code", "")
        if not isinstance(mode, str) or mode not in {"generate", "fix"}:
            self._send_json(400, {"error": "Selecciona generar o corregir código."})
            return
        if not isinstance(language, str) or language not in LANGUAGES:
            self._send_json(400, {"error": "Selecciona un lenguaje de programación válido."})
            return
        if not isinstance(prompt, str) or not prompt.strip():
            self._send_json(400, {"error": "Describe lo que necesitas."})
            return
        if len(prompt) > MAX_PROMPT_CHARS:
            self._send_json(400, {"error": "La descripción no puede superar 4000 caracteres."})
            return
        if not isinstance(code, str):
            self._send_json(400, {"error": "El código debe ser texto."})
            return
        if len(code) > MAX_CODE_CHARS:
            self._send_json(400, {"error": "El código no puede superar 16000 caracteres."})
            return
        if mode == "fix" and not code.strip():
            self._send_json(400, {"error": "Pega el código que quieres corregir."})
            return

        request_body = json.dumps(
            {
                "model": OLLAMA_MODEL,
                "messages": build_messages(mode, language, prompt.strip(), code),
                "stream": False,
                "options": {"temperature": 0.2},
            }
        ).encode("utf-8")
        request = Request(
            f"{OLLAMA_URL}/api/chat",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                result = json.loads(response.read())
            message = result.get("message") if isinstance(result, dict) else None
            answer = message.get("content") if isinstance(message, dict) else None
            if not isinstance(answer, str) or not answer.strip():
                self._send_json(502, {"error": "El modelo local devolvió una respuesta vacía."})
                return
        except HTTPError as error:
            detail = error.read(2048).decode("utf-8", errors="replace")
            self._send_json(502, {"error": self._ollama_error(detail)})
            return
        except (URLError, TimeoutError, OSError):
            self._send_json(
                502,
                {"error": "No se pudo conectar con Ollama. Comprueba que esté iniciado y disponible."},
            )
            return
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(502, {"error": "Ollama devolvió una respuesta que no se pudo leer."})
            return

        self._send_json(200, {"response": answer.strip()})

    def _ollama_error(self, detail):
        try:
            message = json.loads(detail).get("error")
        except (json.JSONDecodeError, AttributeError):
            message = None
        if isinstance(message, str) and message:
            if "not found" in message.lower():
                return (
                    f"No se encontró el modelo «{OLLAMA_MODEL}». "
                    f"Descárgalo con: ollama pull {OLLAMA_MODEL}"
                )
            return f"Ollama informó un error: {message}"
        return "Ollama no pudo responder. Comprueba el modelo configurado y vuelve a intentarlo."

    def _send_json(self, status, payload):
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

def main():
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), CodingAssistantHandler)
    print(f"Asistente disponible en http://{APP_HOST}:{APP_PORT}")
    print(f"Modelo configurado: {OLLAMA_MODEL}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
