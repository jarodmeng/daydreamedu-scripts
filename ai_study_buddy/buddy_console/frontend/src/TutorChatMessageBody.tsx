import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { normalizeAssistantMarkdown } from "./tutorChatMarkdown";

const TUTOR_CHAT_MARKDOWN_COMPONENTS: Components = {
  table: ({ children }) => (
    <div className="tutor-chat-table-wrap">
      <table>{children}</table>
    </div>
  ),
};

type TutorChatMessageBodyProps = {
  role: "student" | "assistant";
  content: string;
  streaming?: boolean;
};

export function TutorChatMessageBody({ role, content, streaming = false }: TutorChatMessageBodyProps) {
  if (!content.trim()) {
    return <div className="tutor-chat-message-body">{streaming ? "…" : ""}</div>;
  }

  if (role === "student") {
    return <div className="tutor-chat-message-body plain">{content}</div>;
  }

  return (
    <div className="tutor-chat-message-body markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={TUTOR_CHAT_MARKDOWN_COMPONENTS}>
        {normalizeAssistantMarkdown(content)}
      </ReactMarkdown>
    </div>
  );
}
