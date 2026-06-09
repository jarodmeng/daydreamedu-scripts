const TUTOR_CHAT_EXPANDED_KEY = "buddy-console-tutor-chat-expanded";

export function readTutorChatExpandedPreference(): boolean {
  try {
    return sessionStorage.getItem(TUTOR_CHAT_EXPANDED_KEY) === "1";
  } catch {
    return false;
  }
}

export function persistTutorChatExpandedPreference(expanded: boolean): void {
  try {
    sessionStorage.setItem(TUTOR_CHAT_EXPANDED_KEY, expanded ? "1" : "0");
  } catch {
    // ignore
  }
}
