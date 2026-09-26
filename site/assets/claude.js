const prompt = document.getElementById("install-prompt");
const copyStatus = document.getElementById("copy-status");
const copyButtons = document.querySelectorAll("[data-copy-prompt]");

for (const button of copyButtons) {
  button.addEventListener("click", async () => {
    const text = prompt.textContent.trim();
    let copied = false;

    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        copied = true;
      } catch {}
    }

    if (!copied) {
      const fallback = document.createElement("textarea");
      fallback.value = text;
      fallback.setAttribute("aria-hidden", "true");
      fallback.tabIndex = -1;
      fallback.style.position = "fixed";
      fallback.style.left = "-9999px";
      document.body.append(fallback);
      fallback.select();
      try {
        copied = document.execCommand("copy");
      } catch {
        copied = false;
      }
      fallback.remove();
    }

    for (const copyButton of copyButtons) {
      copyButton.textContent = copied ? "Prompt copied" : "Copy the setup prompt";
    }

    copyStatus.textContent = copied
      ? "Copied. Open Claude Code and paste the prompt into a new session."
      : "Copy was unavailable. Select and copy the prompt shown above.";
  });
}
