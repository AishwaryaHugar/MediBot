import { ChatResponse } from "../lib/api";
import SourceCitation from "./SourceCitation";

interface Message {
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
}

interface Props {
  message: Message;
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[75%] bg-brand-600 text-white rounded-2xl rounded-br-sm px-4 py-3 text-sm shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  const res = message.response;
  const isSQL = res?.retrieval_type === "sql_rag";

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[82%]">
        <div className="flex items-center gap-2 mb-1.5">
          <div className="w-6 h-6 bg-brand-600 rounded-full flex items-center justify-center text-white text-xs font-bold">M</div>
          <span className="text-xs text-gray-400">MediBot</span>
          {res && (
            <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${isSQL ? "bg-purple-100 text-purple-700" : "bg-teal-100 text-teal-700"}`}>
              {isSQL ? "SQL Analytics" : "Knowledge Base"}
            </span>
          )}
        </div>
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-800 shadow-sm whitespace-pre-wrap">
          {message.content}
          {res?.sources && <SourceCitation sources={res.sources} />}
        </div>
      </div>
    </div>
  );
}

export type { Message };
