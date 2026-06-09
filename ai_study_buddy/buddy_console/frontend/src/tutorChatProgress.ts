export const TUTOR_CHAT_CLIENT_TIMEOUT_MS = 120_000;

export const TUTOR_CHAT_TIMEOUT_MESSAGE =
  "No reply yet after 2 minutes. The server may still be working — refresh the page to check, or try again.";

export const TUTOR_CHAT_CANCEL_MESSAGE = "Stopped waiting for a reply. You can send another message.";

export function formatThinkingStatus(elapsedSec: number): string {
  if (elapsedSec < 45) {
    return `Thinking… ${elapsedSec}s`;
  }
  if (elapsedSec < 90) {
    return `Still working… ${elapsedSec}s`;
  }
  return `Taking longer than usual… ${elapsedSec}s`;
}

export function thinkingHintText(elapsedSec: number, hasPriorAssistantMessage: boolean): string | null {
  if (elapsedSec > 5) {
    return null;
  }
  if (hasPriorAssistantMessage) {
    return "Follow-up replies are usually faster.";
  }
  return "First replies often take 20–40 seconds.";
}
