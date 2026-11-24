const control = document.querySelector(".plane-control");
const status = document.getElementById("viewer-status");
const scans = [
  {
    element: document.getElementById("clinical-view"),
    prefix: "clinical",
    description: "clinical CT of a public ex vivo lumbar vertebra, with relatively coarse trabecular detail",
  },
  {
    element: document.getElementById("micro-view"),
    prefix: "micro",
    description: "Micro-PCCT of the same public ex vivo lumbar vertebra, showing finer trabecular detail",
  },
];

let selection = 0;

control.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-plane]");
  if (!button) return;

  const currentSelection = ++selection;
  const plane = button.dataset.plane;
  if (button.getAttribute("aria-pressed") === "true") {
    status.textContent = `Showing ${plane} views.`;
    return;
  }

  const label = button.textContent;
  status.textContent = `Loading ${plane} views.`;

  try {
    const images = await Promise.all(scans.map(async ({ prefix }) => {
      const image = new Image();
      image.src = `./assets/${prefix}-${plane}.png`;
      await image.decode();
      return image;
    }));
    if (currentSelection !== selection) return;

    scans.forEach(({ element, description }, index) => {
      const image = images[index];
      element.width = image.naturalWidth;
      element.height = image.naturalHeight;
      element.src = image.src;
      element.alt = `${label} ${description}`;
    });
    for (const option of control.querySelectorAll("button")) {
      option.setAttribute("aria-pressed", String(option === button));
    }
    status.textContent = `Showing ${plane} views.`;
  } catch {
    if (currentSelection === selection) status.textContent = `The ${plane} views could not be loaded.`;
  }
});
control.hidden = false;
