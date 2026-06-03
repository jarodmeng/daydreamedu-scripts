import { useEffect, useRef } from "react";

type MultiSelectFilterProps = {
  label: string;
  options: string[];
  selected: string[];
  counts?: Record<string, number>;
  onChange: (next: string[]) => void;
  formatOption?: (value: string) => string;
};

function labelWithCount(text: string, value: string, counts?: Record<string, number>, allKey = "all"): string {
  if (!counts) return text;
  const key = value === "" ? "" : value === "all" ? allKey : value;
  const count = counts[key];
  return typeof count === "number" ? `${text} (${count})` : text;
}

function summaryLabel(
  selected: string[],
  counts: Record<string, number> | undefined,
  formatOption: (value: string) => string,
): string {
  if (selected.length === 0) {
    return labelWithCount("All", "all", counts);
  }
  if (selected.length === 1) {
    const value = selected[0];
    return labelWithCount(formatOption(value), value, counts);
  }
  return `${selected.length} selected`;
}

export default function MultiSelectFilter({
  label,
  options,
  selected,
  counts,
  onChange,
  formatOption = (value) => value,
}: MultiSelectFilterProps) {
  const rootRef = useRef<HTMLLabelElement>(null);
  const detailsRef = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    const details = detailsRef.current;
    if (!details) return;
    function onToggle() {
      if (!details.open) return;
      const filters = details.closest(".filters");
      if (!filters) return;
      filters.querySelectorAll("details.multi-select[open]").forEach((node) => {
        if (node !== details) node.removeAttribute("open");
      });
    }
    details.addEventListener("toggle", onToggle);
    return () => details.removeEventListener("toggle", onToggle);
  }, []);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent): void {
      const root = rootRef.current;
      const details = detailsRef.current;
      if (!details?.open || !root) return;
      const target = event.target;
      if (target instanceof Node && root.contains(target)) return;
      details.removeAttribute("open");
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  function toggle(value: string): void {
    let next: string[];
    if (selected.includes(value)) {
      next = selected.filter((v) => v !== value);
    } else {
      next = [...selected, value];
    }
    if (options.length > 0 && next.length >= options.length) {
      const allowed = new Set(options);
      if (next.every((v) => allowed.has(v))) {
        onChange([]);
        return;
      }
    }
    onChange(next);
  }

  function selectAll(): void {
    onChange([]);
  }

  function stopPanelToggle(event: React.MouseEvent): void {
    event.stopPropagation();
  }

  return (
    <label ref={rootRef} className="multi-select-filter">
      <span>{label}</span>
      <details ref={detailsRef} className="multi-select">
        <summary>{summaryLabel(selected, counts, formatOption)}</summary>
        <div
          className="multi-select-panel"
          role="group"
          aria-label={label}
          onClick={stopPanelToggle}
        >
          <label className="multi-select-option">
            <input type="checkbox" checked={selected.length === 0} onChange={selectAll} />
            <span>{labelWithCount("All", "all", counts)}</span>
          </label>
          {options.map((value) => (
            <label key={value} className="multi-select-option">
              <input
                type="checkbox"
                checked={selected.includes(value)}
                onChange={() => toggle(value)}
              />
              <span>{labelWithCount(formatOption(value), value, counts)}</span>
            </label>
          ))}
        </div>
      </details>
    </label>
  );
}
