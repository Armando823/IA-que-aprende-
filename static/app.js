const form = document.querySelector("#assistant-form");
const codeField = document.querySelector("#code-field");
const codeInput = document.querySelector("#code");
const submitButton = document.querySelector("#submit-button");
const buttonLabel = document.querySelector("#button-label");
const statusMessage = document.querySelector("#status");
const resultPanel = document.querySelector("#result-panel");
const result = document.querySelector("#result");
const copyButton = document.querySelector("#copy-button");

function selectedMode() {
  return form.elements.mode.value;
}

function updateMode() {
  const fixing = selectedMode() === "fix";
  codeField.hidden = !fixing;
  codeInput.required = fixing;
  buttonLabel.textContent = fixing ? "Corregir código" : "Generar código";
}

form.addEventListener("change", (event) => {
  if (event.target.name === "mode") updateMode();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  statusMessage.textContent = "";
  statusMessage.classList.remove("error");
  resultPanel.hidden = true;
  submitButton.disabled = true;
  buttonLabel.textContent = "Pensando...";

  const payload = {
    mode: selectedMode(),
    language: form.elements.language.value,
    prompt: form.elements.prompt.value,
    code: codeInput.value,
  };

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "No se pudo obtener una respuesta.");

    result.textContent = data.response;
    resultPanel.hidden = false;
    statusMessage.textContent = "Respuesta lista.";
  } catch (error) {
    statusMessage.textContent = error.message || "Ocurrió un error inesperado.";
    statusMessage.classList.add("error");
  } finally {
    submitButton.disabled = false;
    buttonLabel.textContent = selectedMode() === "fix" ? "Corregir código" : "Generar código";
  }
});

copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(result.textContent);
    copyButton.textContent = "Copiado";
    window.setTimeout(() => {
      copyButton.textContent = "Copiar";
    }, 1600);
  } catch {
    statusMessage.textContent = "No se pudo copiar. Selecciona y copia el texto manualmente.";
    statusMessage.classList.add("error");
  }
});
