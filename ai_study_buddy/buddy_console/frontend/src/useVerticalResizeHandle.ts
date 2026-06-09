import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_HEIGHT = 340;
const MIN_HEIGHT = 200;

function clampHeight(value: number, getMaxHeight?: () => number): number {
  const maxHeight = getMaxHeight ? getMaxHeight() : DEFAULT_HEIGHT;
  return Math.min(maxHeight, Math.max(MIN_HEIGHT, value));
}

function readStoredHeight(storageKey: string, getMaxHeight?: () => number): number {
  try {
    const raw = sessionStorage.getItem(storageKey);
    const parsed = raw ? Number(raw) : Number.NaN;
    if (Number.isFinite(parsed)) {
      return clampHeight(parsed, getMaxHeight);
    }
  } catch {
    // ignore
  }
  return DEFAULT_HEIGHT;
}

export function useVerticalResizeHandle(storageKey: string, getMaxHeight?: () => number) {
  const getMaxHeightRef = useRef(getMaxHeight);
  getMaxHeightRef.current = getMaxHeight;

  const [panelHeight, setPanelHeightState] = useState<number>(() => readStoredHeight(storageKey, getMaxHeight));

  const panelHeightRef = useRef(panelHeight);
  const dragRef = useRef<{ startY: number; startHeight: number } | null>(null);

  const setPanelHeight = useCallback((value: number | ((prev: number) => number)) => {
    setPanelHeightState((prev) => {
      const next = typeof value === "function" ? value(prev) : value;
      return clampHeight(next, getMaxHeightRef.current);
    });
  }, []);

  useEffect(() => {
    panelHeightRef.current = panelHeight;
  }, [panelHeight]);

  useEffect(() => {
    setPanelHeight((prev) => prev);
  }, [getMaxHeight, setPanelHeight]);

  const endDrag = useCallback(() => {
    dragRef.current = null;
    document.body.style.removeProperty("cursor");
    document.body.style.removeProperty("user-select");
  }, []);

  const onMouseMove = useCallback((event: MouseEvent) => {
    const drag = dragRef.current;
    if (!drag) {
      return;
    }
    const delta = drag.startY - event.clientY;
    const maxHeight = getMaxHeightRef.current ? getMaxHeightRef.current() : DEFAULT_HEIGHT;
    const next = Math.min(maxHeight, Math.max(MIN_HEIGHT, drag.startHeight + delta));
    setPanelHeightState(next);
    panelHeightRef.current = next;
  }, []);

  const onMouseUp = useCallback(() => {
    if (!dragRef.current) {
      return;
    }
    endDrag();
    try {
      sessionStorage.setItem(storageKey, String(panelHeightRef.current));
    } catch {
      // ignore
    }
  }, [endDrag, storageKey]);

  useEffect(() => {
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      endDrag();
    };
  }, [endDrag, onMouseMove, onMouseUp]);

  const startResize = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      event.preventDefault();
      dragRef.current = { startY: event.clientY, startHeight: panelHeightRef.current };
      document.body.style.cursor = "ns-resize";
      document.body.style.userSelect = "none";
    },
    [],
  );

  return { panelHeight, setPanelHeight, startResize };
}
