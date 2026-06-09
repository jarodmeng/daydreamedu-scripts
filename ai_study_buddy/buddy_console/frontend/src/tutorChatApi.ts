export const TUTOR_CHAT_ENABLED = import.meta.env.VITE_REVIEW_TUTOR_CHAT === "1";

export type TutorChatMessage = {
  role: "student" | "assistant";
  content: string;
  at: string;
  model?: string;
  runtime?: string;
  run_id?: string;
};

export type StaleContext = {
  marking: boolean;
  review_notes: boolean;
};

export type TutorChatSessionResponse = {
  session_id: string;
  messages: TutorChatMessage[];
  stale_context: StaleContext;
};

export type TutorChatSseEvent =
  | { type: "status"; phase: string }
  | { type: "token"; text: string }
  | { type: "done"; sessionId: string; staleContext: StaleContext; message: TutorChatMessage }
  | { type: "error"; code: string; message: string };

function tutorChatBasePath(attemptId: string, resultId: string): string {
  return `/api/student/attempts/${encodeURIComponent(attemptId)}/questions/${encodeURIComponent(resultId)}/tutor-chat`;
}

function parseSseData(eventName: string, dataLine: string): TutorChatSseEvent | null {
  let payload: unknown;
  try {
    payload = JSON.parse(dataLine);
  } catch {
    return null;
  }
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const row = payload as Record<string, unknown>;

  if (eventName === "status" && typeof row.phase === "string") {
    return { type: "status", phase: row.phase };
  }
  if (eventName === "token" && typeof row.text === "string") {
    return { type: "token", text: row.text };
  }
  if (eventName === "error") {
    return {
      type: "error",
      code: typeof row.code === "string" ? row.code : "run_failed",
      message: typeof row.message === "string" ? row.message : "Tutor chat failed",
    };
  }
  if (eventName === "done" && typeof row.session_id === "string") {
    const message = row.message;
    if (!message || typeof message !== "object") {
      return null;
    }
    const msg = message as Record<string, unknown>;
    if (typeof msg.content !== "string" || typeof msg.at !== "string") {
      return null;
    }
    const stale = row.stale_context;
    const staleContext: StaleContext = {
      marking: Boolean(stale && typeof stale === "object" && (stale as StaleContext).marking),
      review_notes: Boolean(stale && typeof stale === "object" && (stale as StaleContext).review_notes),
    };
    return {
      type: "done",
      sessionId: row.session_id,
      staleContext,
      message: {
        role: msg.role === "assistant" ? "assistant" : "student",
        content: msg.content,
        at: msg.at,
        model: typeof msg.model === "string" ? msg.model : undefined,
        runtime: typeof msg.runtime === "string" ? msg.runtime : undefined,
        run_id: typeof msg.run_id === "string" ? msg.run_id : undefined,
      },
    };
  }
  return null;
}

export function parseSseEvents(raw: string): TutorChatSseEvent[] {
  const events: TutorChatSseEvent[] = [];
  const blocks = raw.split("\n\n");
  for (const block of blocks) {
    const trimmed = block.trim();
    if (!trimmed) {
      continue;
    }
    let eventName = "message";
    let dataLine = "";
    for (const line of trimmed.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLine = line.slice(5).trim();
      }
    }
    if (!dataLine) {
      continue;
    }
    const parsed = parseSseData(eventName, dataLine);
    if (parsed) {
      events.push(parsed);
    }
  }
  return events;
}

export function splitSseBuffer(buffer: string): { events: TutorChatSseEvent[]; remainder: string } {
  const lastDelimiter = buffer.lastIndexOf("\n\n");
  if (lastDelimiter < 0) {
    return { events: [], remainder: buffer };
  }
  const complete = buffer.slice(0, lastDelimiter + 2);
  const remainder = buffer.slice(lastDelimiter + 2);
  return { events: parseSseEvents(complete), remainder };
}

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const payload = (await res.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // fall through
  }
  return `Request failed (${res.status})`;
}

export async function fetchLatestTutorChatSession(
  attemptId: string,
  resultId: string,
): Promise<TutorChatSessionResponse | null> {
  const res = await fetch(tutorChatBasePath(attemptId, resultId));
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(await readErrorMessage(res));
  }
  return (await res.json()) as TutorChatSessionResponse;
}

export async function createTutorChatSession(attemptId: string, resultId: string): Promise<string> {
  const res = await fetch(`${tutorChatBasePath(attemptId, resultId)}/sessions`, { method: "POST" });
  if (!res.ok) {
    throw new Error(await readErrorMessage(res));
  }
  const payload = (await res.json()) as { session_id?: string };
  if (!payload.session_id) {
    throw new Error("Missing session_id");
  }
  return payload.session_id;
}

export async function streamTutorChatMessage(
  params: {
    attemptId: string;
    resultId: string;
    message: string;
    sessionId?: string | null;
    refreshContext?: boolean;
  },
  onEvent: (event: TutorChatSseEvent) => void,
  options?: { signal?: AbortSignal },
): Promise<void> {
  const res = await fetch(tutorChatBasePath(params.attemptId, params.resultId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: params.message,
      session_id: params.sessionId ?? undefined,
      refresh_context: params.refreshContext ?? false,
    }),
    signal: options?.signal,
  });
  if (!res.ok) {
    throw new Error(await readErrorMessage(res));
  }
  if (!res.body) {
    throw new Error("No response body");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const { events, remainder } = splitSseBuffer(buffer);
    buffer = remainder;
    for (const event of events) {
      onEvent(event);
    }
  }
  buffer += decoder.decode();
  if (buffer.trim()) {
    for (const event of parseSseEvents(buffer)) {
      onEvent(event);
    }
  }
}

export function staleContextActive(stale: StaleContext | null | undefined): boolean {
  if (!stale) {
    return false;
  }
  return stale.marking || stale.review_notes;
}
