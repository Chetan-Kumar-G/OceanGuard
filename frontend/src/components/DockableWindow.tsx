import { useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

let zCounter = 100;
let cascadeCounter = 0;

interface Props {
  title: string;
  children: ReactNode;
  headerActions?: ReactNode;
  /** Size while floating. Body scrolls internally if content exceeds it. */
  floatingSize?: { width: number; height: number };
  className?: string;
  /** Controlled mode - pass both, or neither (uncontrolled, manages its own state). */
  detached?: boolean;
  onToggleDetached?: (next: boolean) => void;
}

/**
 * Wraps a dashboard panel so it can be "detached" into a draggable floating
 * window (rendered via a portal to <body>, so it isn't clipped by the panel's
 * normal scroll container) and "attached" back into the grid layout.
 */
export default function DockableWindow({
  title,
  children,
  headerActions,
  floatingSize,
  className,
  detached: detachedProp,
  onToggleDetached,
}: Props) {
  const [internalDetached, setInternalDetached] = useState(false);
  const isControlled = detachedProp !== undefined;
  const detached = isControlled ? detachedProp : internalDetached;

  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [z, setZ] = useState(zCounter);
  const dragOffset = useRef<{ dx: number; dy: number } | null>(null);
  const size = floatingSize ?? { width: 420, height: 460 };

  function setDetached(next: boolean) {
    if (isControlled) onToggleDetached?.(next);
    else setInternalDetached(next);
  }

  function bringToFront() {
    zCounter += 1;
    setZ(zCounter);
  }

  function detach() {
    if (pos == null) {
      cascadeCounter = (cascadeCounter + 1) % 8;
      setPos({ x: 140 + cascadeCounter * 24, y: 120 + cascadeCounter * 24 });
    }
    bringToFront();
    setDetached(true);
  }

  function onTitleMouseDown(e: React.MouseEvent) {
    if ((e.target as HTMLElement).closest("button")) return;
    bringToFront();
    const current = pos ?? { x: 140, y: 120 };
    dragOffset.current = { dx: e.clientX - current.x, dy: e.clientY - current.y };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }

  function onMouseMove(e: MouseEvent) {
    if (!dragOffset.current) return;
    setPos({
      x: Math.max(0, e.clientX - dragOffset.current.dx),
      y: Math.max(0, e.clientY - dragOffset.current.dy),
    });
  }

  function onMouseUp() {
    dragOffset.current = null;
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
  }

  const titleBar = (
    <div className="dock-titlebar" onMouseDown={detached ? onTitleMouseDown : undefined}>
      <span className="dock-title">{title}</span>
      <div className="dock-actions">
        {headerActions}
        <button className="dock-toggle" onClick={() => (detached ? setDetached(false) : detach())} title={detached ? "Attach" : "Detach"}>
          {detached ? "⧉ Attach" : "⤢ Detach"}
        </button>
      </div>
    </div>
  );

  if (!detached) {
    return (
      <div className={`dock-window dock-attached ${className ?? ""}`}>
        {titleBar}
        <div className="dock-body">{children}</div>
      </div>
    );
  }

  return (
    <>
      <div className="dock-placeholder">
        <span>↗ {title} is floating</span>
        <button className="link-button" onClick={() => setDetached(false)}>
          Reattach
        </button>
      </div>
      {createPortal(
        <div
          className={`dock-window dock-floating ${className ?? ""}`}
          style={{ left: pos?.x ?? 140, top: pos?.y ?? 120, width: size.width, zIndex: z }}
          onMouseDownCapture={bringToFront}
        >
          {titleBar}
          <div className="dock-body dock-body-floating" style={{ height: size.height }}>
            {children}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
