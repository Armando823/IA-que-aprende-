# Asistente local de programación

Aplicación web sencilla en español para generar código o pedir ayuda para corregirlo. Usa un modelo de programación abierto servido localmente por [Ollama](https://ollama.com/); las consultas no se envían a una API alojada y el código generado no se ejecuta.

## Requisitos

- Python 3.10 o posterior.
- [Ollama](https://ollama.com/download) instalado y en ejecución.
- El modelo `qwen2.5-coder:3b` (aproximadamente 2 GB de descarga; el uso de memoria depende de tu equipo).

## Iniciar en Windows

Abre PowerShell en la carpeta del proyecto y descarga el modelo:

```powershell
ollama pull qwen2.5-coder:3b
```

Si Ollama no está ejecutándose, inicia el servicio en otra ventana:

```powershell
ollama serve
```

Inicia la aplicación:

```powershell
python app.py
```

Abre <http://127.0.0.1:8000> en el navegador. Detén el servidor con `Ctrl+C`.

## Configuración

La aplicación usa `http://127.0.0.1:11434` para Ollama y `qwen2.5-coder:3b` como modelo por defecto. Puedes configurarlos con variables de entorno antes de iniciar el servidor:

```powershell
$env:OLLAMA_MODEL = "qwen2.5-coder:7b"
$env:OLLAMA_URL = "http://127.0.0.1:11434"
$env:APP_PORT = "8000"
python app.py
```

Descarga cualquier modelo alternativo antes de usarlo (por ejemplo, `ollama pull qwen2.5-coder:7b`). La interfaz y la API se enlazan a `127.0.0.1` por defecto para que solo sean accesibles desde el equipo local.

## Comprobaciones

Ejecuta las pruebas integradas con la biblioteca estándar de Python:

```powershell
python -m unittest
```
