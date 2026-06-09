import { useEffect, useRef, useState } from "react";

import {
  createTutorChatSession,
  fetchLatestTutorChatSession,
  staleContextActive,
  streamTutorChatMessage,
  type StaleContext,
  type TutorChatMessage,
} from "./tutorChatApi";
import { TutorChatMessageBody } from "./TutorChatMessageBody";
import { persistTutorChatExpandedPreference } from "./tutorChatPrefs";
import {
  formatThinkingStatus,
  thinkingHintText,
  TUTOR_CHAT_CANCEL_MESSAGE,
  TUTOR_CHAT_CLIENT_TIMEOUT_MS,
  TUTOR_CHAT_TIMEOUT_MESSAGE,
} from "./tutorChatProgress";

type TutorChatPanelProps = {
  attemptId: string;
  resultId: string;
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
};

function formatMessageTime(at: string): string {
  const parsed = Date.parse(at);
  if (Number.isNaN(parsed)) {
    return "";
  }
  return new Date(parsed).toLocaleString();
}

export function TutorChatPanel({ attemptId, resultId, expanded, onExpandedChange }: TutorChatPanelProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TutorChatMessage[]>([]);
  const [staleContext, setStaleContext] = useState<StaleContext>({ marking: false, review_notes: false });
  const [draft, setDraft] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [sending, setSending] = useState<boolean>(false);
  const [thinkingElapsedSec, setThinkingElapsedSec] = useState<number>(0);
  const [backendAlive, setBackendAlive] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingRefresh, setPendingRefresh] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const abortReasonRef = useRef<"timeout" | "cancel" | null>(null);

  function setExpanded(next: boolean) {
    onExpandedChange(next);
    persistTutorChatExpandedPreference(next);
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDraft("");
    setPendingRefresh(false);
    setMessages([]);
    setSessionId(null);
    setStaleContext({ marking: false, review_notes: false });

    void (async () => {
      try {
        const session = await fetchLatestTutorChatSession(attemptId, resultId);
        if (cancelled) {
          return;
        }
        if (session) {
          setSessionId(session.session_id);
          setMessages(session.messages ?? []);
          setStaleContext(session.stale_context ?? { marking: false, review_notes: false });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load tutor chat");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [attemptId, resultId]);

  useEffect(() => {
    if (expanded) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, expanded, sending]);

  useEffect(() => {
    if (!sending) {
      setThinkingElapsedSec(0);
      setBackendAlive(false);
      return;
    }

    const startedAt = Date.now();
    setThinkingElapsedSec(0);
    const timerId = window.setInterval(() => {
      setThinkingElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => {
      window.clearInterval(timerId);
    };
  }, [sending]);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  function cancelInFlight() {
    if (!sending) {
      return;
    }
    abortReasonRef.current = "cancel";
    abortControllerRef.current?.abort();
  }

  async function startNewConversation() {
    setError(null);
    setSending(true);
    try {
      const newSessionId = await createTutorChatSession(attemptId, resultId);
      setSessionId(newSessionId);
      setMessages([]);
      setStaleContext({ marking: false, review_notes: false });
      setPendingRefresh(false);
      setExpanded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start new conversation");
    } finally {
      setSending(false);
    }
  }

  async function sendMessage() {
    const text = draft.trim();
    if (!text || sending) {
      return;
    }

    const studentMessage: TutorChatMessage = {
      role: "student",
      content: text,
      at: new Date().toISOString(),
    };
    const assistantPlaceholder: TutorChatMessage = {
      role: "assistant",
      content: "",
      at: new Date().toISOString(),
    };

    setDraft("");
    setError(null);
    setSending(true);
    setMessages((prev) => [...prev, studentMessage, assistantPlaceholder]);

    const refreshContext = pendingRefresh;
    if (refreshContext) {
      setPendingRefresh(false);
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    abortReasonRef.current = null;

    const timeoutId = window.setTimeout(() => {
      abortReasonRef.current = "timeout";
      abortController.abort();
    }, TUTOR_CHAT_CLIENT_TIMEOUT_MS);

    try {
      await streamTutorChatMessage(
        {
          attemptId,
          resultId,
          message: text,
          sessionId,
          refreshContext,
        },
        (event) => {
          if (event.type === "status") {
            setBackendAlive(true);
            return;
          }
          if (event.type === "token") {
            setMessages((prev) => {
              if (prev.length === 0) {
                return prev;
              }
              const next = [...prev];
              const last = next[next.length - 1];
              if (last.role !== "assistant") {
                return prev;
              }
              next[next.length - 1] = { ...last, content: `${last.content}${event.text}` };
              return next;
            });
            return;
          }
          if (event.type === "error") {
            throw new Error(event.message);
          }
          if (event.type === "done") {
            setSessionId(event.sessionId);
            setStaleContext(event.staleContext);
            setMessages((prev) => {
              if (prev.length === 0) {
                return [event.message];
              }
              const next = [...prev];
              next[next.length - 1] = event.message;
              return next;
            });
          }
        },
        { signal: abortController.signal },
      );
    } catch (err) {
      if (abortController.signal.aborted) {
        setError(abortReasonRef.current === "timeout" ? TUTOR_CHAT_TIMEOUT_MESSAGE : TUTOR_CHAT_CANCEL_MESSAGE);
      } else {
        setError(err instanceof Error ? err.message : "Failed to send message");
      }
      setMessages((prev) => {
        if (prev.length < 2) {
          return prev.slice(0, -1);
        }
        const last = prev[prev.length - 1];
        if (last.role === "assistant" && !last.content.trim()) {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      window.clearTimeout(timeoutId);
      abortControllerRef.current = null;
      abortReasonRef.current = null;
      setSending(false);
    }
  }

  const showStaleBanner = staleContextActive(staleContext) && !pendingRefresh;
  const hasPriorAssistantMessage = messages.some((message) => message.role === "assistant");
  const thinkingHint = sending ? thinkingHintText(thinkingElapsedSec, hasPriorAssistantMessage) : null;

  return (
    <article className={`tutor-chat ${expanded ? "expanded" : "collapsed"}`}>
      <div className="tutor-chat-head">
        <div className="tutor-chat-title-row">
          <strong>Ask AI</strong>
          {sending ? (
            <span className="tutor-chat-status-pill" role="status">
              {formatThinkingStatus(thinkingElapsedSec)}
            </span>
          ) : null}
        </div>
        <div className="tutor-chat-head-actions">
          <button type="button" className="tutor-chat-toggle" disabled={sending} onClick={() => void startNewConversation()}>
            New conversation
          </button>
          <button
            type="button"
            className="tutor-chat-toggle"
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "Hide chat" : "Ask AI"}
          </button>
        </div>
      </div>

      {expanded ? (
        <div className="tutor-chat-body">
          <p className="tutor-chat-disclaimer">AI may be wrong — check with parent or teacher.</p>

          {showStaleBanner ? (
            <div className="tutor-chat-stale-banner" role="status">
              <span>Marking or review notes changed since this chat started.</span>
              <button type="button" disabled={sending} onClick={() => setPendingRefresh(true)}>
                Refresh &amp; continue
              </button>
            </div>
          ) : null}

          {pendingRefresh ? (
            <p className="tutor-chat-refresh-note">Context will refresh on your next message.</p>
          ) : null}

          {loading ? <p className="tutor-chat-meta">Loading chat…</p> : null}
          {error ? <p className="tutor-chat-error">{error}</p> : null}
          {thinkingHint ? <p className="tutor-chat-meta">{thinkingHint}</p> : null}
          {sending && backendAlive ? <p className="tutor-chat-meta">Tutor is working on your question…</p> : null}

          <div className="tutor-chat-messages" aria-live="polite">
            {messages.length === 0 && !loading ? (
              <p className="tutor-chat-meta">Ask why you got this question wrong, or how to fix your approach.</p>
            ) : null}
            {messages.map((message, index) => (
              <div key={`${message.at}-${index}`} className={`tutor-chat-message ${message.role}`}>
                <div className="tutor-chat-message-meta">
                  <span>{message.role === "student" ? "You" : "Tutor"}</span>
                  <time dateTime={message.at}>{formatMessageTime(message.at)}</time>
                </div>
                <TutorChatMessageBody
                  role={message.role}
                  content={message.content}
                  streaming={sending && message.role === "assistant" && index === messages.length - 1}
                />
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <form
            className="tutor-chat-input-row"
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage();
            }}
          >
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask about this question…"
              rows={2}
              disabled={sending || loading}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
            />
            {sending ? (
              <button type="button" className="tutor-chat-cancel" onClick={cancelInFlight}>
                Stop
              </button>
            ) : (
              <button type="submit" disabled={loading || !draft.trim()}>
                Send
              </button>
            )}
          </form>
        </div>
      ) : null}
    </article>
  );
}
