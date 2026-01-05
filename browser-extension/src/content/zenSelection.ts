// Zen browser-like selection feature
// Custom drag selection without external libraries

interface SelectionOptions {
  onComplete?: (selectedText: string, selectedElements: HTMLElement[]) => void;
  onCancel?: () => void;
}

export class ZenSelection {
  private overlay: HTMLElement | null = null;
  private cancelButton: HTMLElement | null = null;
  private instructionText: HTMLElement | null = null;
  private highlightBox: HTMLElement | null = null;
  private hoverOverlay: HTMLElement | null = null;
  private isActive: boolean = false;
  private options: SelectionOptions;

  constructor(options: SelectionOptions = {}) {
    this.options = options;
  }

  public start() {
    if (this.isActive) return;
    this.isActive = true;

    this.createOverlay();
    this.createCancelButton();
    this.createInstructionText();
    this.createHighlightBox();
    this.initializeSelecto();
    this.addKeyboardListeners();

    console.log("🎯 Zen Selection Mode Activated");
  }

  private getHoverOverlay(): HTMLElement {
    if (!this.hoverOverlay) {
      this.hoverOverlay = document.createElement("div");
      this.hoverOverlay.style.cssText = `
      position: fixed;
      pointer-events: none;
      z-index: 2147483647;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.2);
      backdrop-filter: blur(0px);
      -webkit-backdrop-filter: blur(3px);
      box-shadow: 0 0 0 2px rgba(11, 133, 255, 0.47);
      transition: all .08s ease;
    `;
      document.body.appendChild(this.hoverOverlay);
    }
    return this.hoverOverlay;
  }

  private createOverlay() {
    this.overlay = document.createElement("div");
    this.overlay.id = "canner-zen-overlay";
    this.overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(0, 0, 0, 0.4);
      backdrop-filter: blur(0.5px);
      z-index: 2147483646;
      cursor: crosshair;
      transition: background 0.3s ease;
    `;

    document.body.appendChild(this.overlay);
  }

  private createCancelButton() {
    this.cancelButton = document.createElement("button");
    this.cancelButton.textContent = "Cancel";
    this.cancelButton.style.cssText = `
      position: fixed;
      bottom: 40px;
      left: 50%;
      transform: translateX(-50%);
      padding: 12px 32px;
      background: rgba(255, 255, 255, 0.95);
      border: 2px solid rgba(0, 0, 0, 0.1);
      border-radius: 8px;
      color: #333;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      z-index: 2147483647;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      transition: all 0.2s ease;
    `;

    this.cancelButton.addEventListener("mouseenter", () => {
      if (this.cancelButton) {
        this.cancelButton.style.background = "rgba(255, 255, 255, 1)";
        this.cancelButton.style.transform = "translateX(-50%) scale(1.05)";
      }
    });

    this.cancelButton.addEventListener("mouseleave", () => {
      if (this.cancelButton) {
        this.cancelButton.style.background = "rgba(255, 255, 255, 0.95)";
        this.cancelButton.style.transform = "translateX(-50%) scale(1)";
      }
    });

    this.cancelButton.addEventListener("click", () => {
      this.cancel();
    });

    document.body.appendChild(this.cancelButton);
  }

  private createInstructionText() {
    this.instructionText = document.createElement("div");
    this.instructionText.style.cssText = `
      position: fixed;
      top: 40px;
      left: 50%;
      transform: translateX(-50%);
      padding: 16px 32px;
      background: rgba(255, 255, 255, 0.95);
      border-radius: 8px;
      color: #333;
      font-size: 16px;
      font-weight: 500;
      z-index: 2147483647;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      text-align: center;
      pointer-events: none;
    `;
    this.instructionText.innerHTML = `
      <div style="font-size: 18px; margin-bottom: 8px;">Select Content</div>
      <div style="font-size: 14px; opacity: 0.8;">Drag to select or click on any element • Press <kbd style="padding: 2px 6px; background: #f0f0f0; border-radius: 4px; font-weight: 600;">ESC</kbd> to cancel</div>
    `;

    document.body.appendChild(this.instructionText);
  }

  private createHighlightBox() {
    this.highlightBox = document.createElement("div");
    this.highlightBox.style.cssText = `
      position: fixed;
      border: 3px solid #0b84ff;
      background: rgba(11, 132, 255, 0.1);
      pointer-events: none;
      z-index: 2147483647;
      display: none;
      border-radius: 4px;
      box-shadow: 0 0 0 2px rgba(11, 132, 255, 0.3);
    `;

    document.body.appendChild(this.highlightBox);
  }

  private initializeSelecto() {
    if (!this.overlay) return;

    let isMouseDown = false;
    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let hoveredElement: HTMLElement | null = null;

    // Mouse move handler for hover preview
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) return;

      // Remove previous hover highlight
      const hoverBox = this.getHoverOverlay();
      hoverBox.style.display = "none";

      // Get element under cursor (excluding overlay)
      const elementsAtPoint = document.elementsFromPoint(e.clientX, e.clientY);
      const targetElement = elementsAtPoint.find(
        (el) =>
          el !== this.overlay &&
          el !== this.highlightBox &&
          el !== this.cancelButton &&
          el !== this.instructionText
      ) as HTMLElement;

      if (targetElement) {
        const selectableElement = this.findSelectableElement(targetElement);
        if (selectableElement) {
          hoveredElement = selectableElement;

          const rect = hoveredElement.getBoundingClientRect();
          const hoverBox = this.getHoverOverlay();

          hoverBox.style.display = "block";
          hoverBox.style.left = rect.left + "px";
          hoverBox.style.top = rect.top + "px";
          hoverBox.style.width = rect.width + "px";
          hoverBox.style.height = rect.height + "px";
        }
      }
    };

    // Mouse down - start drag
    const handleMouseDown = (e: MouseEvent) => {
      // Check if clicking on cancel button or instruction
      if ((e.target as HTMLElement).closest("button, .instruction")) return;

      isMouseDown = true;
      isDragging = false; // Will become true if mouse moves enough
      startX = e.clientX;
      startY = e.clientY;

      // Clear hover highlight when starting drag
      if (hoveredElement) {
        hoveredElement.style.outline = "";
        hoveredElement.style.outlineOffset = "";
      }

      if (this.highlightBox) {
        this.highlightBox.style.left = `${startX}px`;
        this.highlightBox.style.top = `${startY}px`;
        this.highlightBox.style.width = "0px";
        this.highlightBox.style.height = "0px";
      }
    };

    // Mouse move during drag - update selection box
    const handleDragMove = (e: MouseEvent) => {
      if (!isMouseDown || !this.highlightBox) return;

      // Check if mouse moved enough to be considered a drag
      const moveX = Math.abs(e.clientX - startX);
      const moveY = Math.abs(e.clientY - startY);

      if (moveX > 3 || moveY > 3) {
        isDragging = true;
        this.highlightBox.style.display = "block";
      }

      if (isDragging) {
        const x = Math.min(e.clientX, startX);
        const y = Math.min(e.clientY, startY);
        const width = Math.abs(e.clientX - startX);
        const height = Math.abs(e.clientY - startY);

        this.highlightBox.style.left = `${x}px`;
        this.highlightBox.style.top = `${y}px`;
        this.highlightBox.style.width = `${width}px`;
        this.highlightBox.style.height = `${height}px`;
      }
    };

    // Mouse up - complete selection
    const handleMouseUp = (e: MouseEvent) => {
      if (!isMouseDown) return;

      // Check if this was a click (no drag) or a drag selection
      if (!isDragging) {
        // Click selection - get element at click position
        console.log("🖱️ Click detected at", e.clientX, e.clientY);

        const elementsAtPoint = document.elementsFromPoint(
          e.clientX,
          e.clientY
        );

        console.log(
          "📍 Elements at point:",
          elementsAtPoint.map((el) => el.tagName)
        );

        const targetElement = elementsAtPoint.find(
          (el) =>
            el !== this.overlay &&
            el !== this.highlightBox &&
            el !== this.cancelButton &&
            el !== this.instructionText
        ) as HTMLElement;

        if (targetElement) {
          console.log(
            "🎯 Target element:",
            targetElement.tagName,
            targetElement
          );
          const selectableElement = this.findSelectableElement(targetElement);
          if (selectableElement) {
            console.log(
              "✅ Selectable element found:",
              selectableElement.tagName
            );
            this.handleSelection([selectableElement]);
          } else if (!selectableElement) {
            const hoverBox = this.getHoverOverlay();
            hoverBox.style.display = "none";
            return;
          } else {
            console.log("❌ No selectable element found");
          }
        }
      } else {
        // Drag selection
        console.log("📦 Drag selection completed");

        if (this.highlightBox) {
          const rect = this.highlightBox.getBoundingClientRect();
          this.highlightBox.style.display = "none";

          // Find elements within selection box
          if (rect.width > 5 && rect.height > 5) {
            const selectedElements = this.findElementsInRect(rect);
            console.log("📊 Found elements in rect:", selectedElements.length);
            if (selectedElements.length > 0) {
              this.handleSelection(selectedElements);
            }
          }
        }
      }

      // Reset state
      isMouseDown = false;
      isDragging = false;

      // Restore hover if mouse is still over an element
      setTimeout(() => {
        const event = new MouseEvent("mousemove", {
          clientX: e.clientX,
          clientY: e.clientY,
          bubbles: true,
        });
        document.dispatchEvent(event);
      }, 10);
    };

    // Add event listeners
    this.overlay.addEventListener("mousemove", handleMouseMove);
    this.overlay.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("mousemove", handleDragMove);
    document.addEventListener("mouseup", handleMouseUp);

    // Store handlers for cleanup
    (this as any)._mouseHandlers = {
      handleMouseMove,
      handleMouseDown,
      handleDragMove,
      handleMouseUp,
    };
  }

  private findElementsInRect(rect: DOMRect): HTMLElement[] {
    // Prioritize text-content elements over containers
    const selectors = [
      "p",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "li",
      "a",
      "span",
      "code",
      "pre",
      "blockquote",
      "td",
      "th",
    ].join(", ");

    const elements = Array.from(
      document.querySelectorAll<HTMLElement>(selectors)
    );

    const selected: HTMLElement[] = [];
    const addedElements = new Set<HTMLElement>();

    for (const el of elements) {
      // Skip if already added or is a child of an already selected element
      if (addedElements.has(el)) continue;

      const r = el.getBoundingClientRect();

      // Skip if element has no dimensions or no text
      if (r.width === 0 || r.height === 0 || !el.innerText?.trim()) continue;

      // Check if element is substantially within the selection rect
      // Element center should be within the rect, or at least 50% overlap
      const centerX = r.left + r.width / 2;
      const centerY = r.top + r.height / 2;

      const isWithinRect =
        (centerX >= rect.left &&
          centerX <= rect.right &&
          centerY >= rect.top &&
          centerY <= rect.bottom) ||
        // Or check for substantial overlap (at least 50%)
        this.calculateOverlap(r, rect) > 0.5;

      if (isWithinRect) {
        // Check if any parent is already selected
        let hasSelectedParent = false;
        let parent = el.parentElement;
        while (parent && parent !== document.body) {
          if (addedElements.has(parent)) {
            hasSelectedParent = true;
            break;
          }
          parent = parent.parentElement;
        }

        if (!hasSelectedParent) {
          selected.push(el);
          addedElements.add(el);
        }
      }
    }

    return selected;
  }

  private calculateOverlap(elem: DOMRect, selection: DOMRect): number {
    // Calculate the intersection area
    const overlapLeft = Math.max(elem.left, selection.left);
    const overlapTop = Math.max(elem.top, selection.top);
    const overlapRight = Math.min(elem.right, selection.right);
    const overlapBottom = Math.min(elem.bottom, selection.bottom);

    if (overlapLeft >= overlapRight || overlapTop >= overlapBottom) {
      return 0; // No overlap
    }

    const overlapArea =
      (overlapRight - overlapLeft) * (overlapBottom - overlapTop);
    const elemArea = elem.width * elem.height;

    return overlapArea / elemArea;
  }

  private findSelectableElement(element: HTMLElement): HTMLElement | null {
    // Prefer text content elements over large containers
    const preferredTags = [
      "P",
      "H1",
      "H2",
      "H3",
      "H4",
      "H5",
      "H6",
      "LI",
      "A",
      "SPAN",
      "CODE",
      "PRE",
      "BLOCKQUOTE",
      "TD",
      "TH",
    ];

    const acceptableTags = [...preferredTags, "DIV", "ARTICLE", "SECTION"];

    let current: HTMLElement | null = element;
    let bestMatch: HTMLElement | null = null;

    while (current && current !== document.body) {
      if (
        acceptableTags.includes(current.tagName) &&
        current.innerText?.trim()
      ) {
        // For DIV/ARTICLE/SECTION, only select if it's reasonably small
        if (["DIV", "ARTICLE", "SECTION"].includes(current.tagName)) {
          const rect = current.getBoundingClientRect();
          // Only accept container elements if they're not too large (< 50% of viewport)
          const viewportArea = window.innerWidth * window.innerHeight;
          const elementArea = rect.width * rect.height;

          if (elementArea < viewportArea * 0.5) {
            bestMatch = current;
          }
        } else {
          // Preferred element found - return immediately
          return current;
        }
      }
      current = current.parentElement;
    }

    // Return best match if found, otherwise the original element if it has text
    return bestMatch || (element.innerText?.trim() ? element : null);
  }

  private handleSelection(elements: HTMLElement[]) {
    // Extract text from selected elements
    const text = elements
      .map((el) => el.innerText.trim())
      .filter(Boolean)
      .join("\n\n");

    console.log("📥 Selected content:", text);
    console.log("📦 Selected elements:", elements);

    // Call the completion callback
    if (this.options.onComplete) {
      this.options.onComplete(text, elements);
    }

    // Auto-cleanup after selection
    this.cleanup();
  }

  private addKeyboardListeners() {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        this.cancel();
      }
    };

    document.addEventListener("keydown", handleEscape);

    // Store reference to remove later
    (this as any)._escapeHandler = handleEscape;
  }

  private cancel() {
    console.log("❌ Selection cancelled");

    if (this.options.onCancel) {
      this.options.onCancel();
    }

    this.cleanup();
  }

  private cleanup() {
    // Remove mouse handlers
    if ((this as any)._mouseHandlers) {
      const handlers = (this as any)._mouseHandlers;
      this.overlay?.removeEventListener("mousemove", handlers.handleMouseMove);
      this.overlay?.removeEventListener("mousedown", handlers.handleMouseDown);
      document.removeEventListener("mousemove", handlers.handleDragMove);
      document.removeEventListener("mouseup", handlers.handleMouseUp);
      delete (this as any)._mouseHandlers;
    }

    this.hoverOverlay?.remove();
    this.hoverOverlay = null;

    // Remove all visual elements
    this.overlay?.remove();
    this.cancelButton?.remove();
    this.instructionText?.remove();
    this.highlightBox?.remove();

    // Remove keyboard listeners
    if ((this as any)._escapeHandler) {
      document.removeEventListener("keydown", (this as any)._escapeHandler);
      delete (this as any)._escapeHandler;
    }

    // Clean up any lingering outlines
    document.querySelectorAll('[style*="outline"]').forEach((el) => {
      (el as HTMLElement).style.outline = "";
      (el as HTMLElement).style.outlineOffset = "";
    });

    // Reset state
    this.isActive = false;
    this.overlay = null;
    this.cancelButton = null;
    this.instructionText = null;
    this.highlightBox = null;

    console.log("✅ Zen Selection cleaned up");
  }

  public isSelectionActive(): boolean {
    return this.isActive;
  }
}
