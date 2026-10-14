// Global window position is optional on Wayland; resizing is independent.
export async function resizeWindow(win, dpi, width, height) {
  const scale = await win.scaleFactor();
  let position = null;
  let previousSize = null;
  try {
    position = await win.outerPosition();
    previousSize = await win.innerSize();
  } catch { /* compositor does not expose global coordinates */ }
  const physicalWidth = Math.round(width * scale);
  const physicalHeight = Math.round(height * scale);
  await win.setSize(new dpi.PhysicalSize(physicalWidth, physicalHeight));
  if (position && previousSize) {
    try {
      await win.setPosition(new dpi.PhysicalPosition(
        position.x + previousSize.width - physicalWidth,
        position.y + previousSize.height - physicalHeight,
      ));
    } catch { /* position remains controlled by the compositor */ }
  }
}
