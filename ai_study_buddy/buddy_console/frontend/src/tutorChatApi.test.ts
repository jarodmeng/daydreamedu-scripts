import { describe, expect, it } from "vitest";

import { parseSseEvents, splitSseBuffer, staleContextActive } from "./tutorChatApi";

describe("tutorChatApi SSE parsing", () => {
  it("parses token and done events", () => {
    const raw = [
      'event: token\ndata: {"text":"Because "}\n',
      "\n",
      'event: token\ndata: {"text":"roots carry water."}\n',
      "\n",
      'event: done\ndata: {"session_id":"sess-1","stale_context":{"marking":false,"review_notes":false},"message":{"role":"assistant","content":"Because roots carry water.","at":"2026-06-09T10:00:15Z"}}\n',
      "\n",
    ].join("");

    const events = parseSseEvents(raw);
    expect(events).toHaveLength(3);
    expect(events[0]).toEqual({ type: "token", text: "Because " });
    expect(events[1]).toEqual({ type: "token", text: "roots carry water." });
    expect(events[2]?.type).toBe("done");
    if (events[2]?.type === "done") {
      expect(events[2].sessionId).toBe("sess-1");
      expect(events[2].message.content).toBe("Because roots carry water.");
    }
  });

  it("parses error events", () => {
    const events = parseSseEvents('event: error\ndata: {"code":"run_failed","message":"boom"}\n\n');
    expect(events).toEqual([{ type: "error", code: "run_failed", message: "boom" }]);
  });

  it("buffers partial SSE blocks", () => {
    const first = splitSseBuffer('event: token\ndata: {"text":"A"}\n');
    expect(first.events).toEqual([]);
    expect(first.remainder).toContain("event: token");

    const second = splitSseBuffer(`${first.remainder}\n\n`);
    expect(second.events).toEqual([{ type: "token", text: "A" }]);
  });
});

describe("staleContextActive", () => {
  it("returns true when marking or review notes drift", () => {
    expect(staleContextActive({ marking: true, review_notes: false })).toBe(true);
    expect(staleContextActive({ marking: false, review_notes: true })).toBe(true);
    expect(staleContextActive({ marking: false, review_notes: false })).toBe(false);
  });
});
