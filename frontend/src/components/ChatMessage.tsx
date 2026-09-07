import type { Source } from "@/lib/api";

export interface ChatMessageData {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  retrievalType?: "hybrid_rag" | "sql_rag";
  isError?: boolean;
}

const RETRIEVAL_LABEL: Record<"hybrid_rag" | "sql_rag", string> = {
  hybrid_rag: "Hybrid RAG",
  sql_rag: "SQL RAG",
};

const RETRIEVAL_STYLE: Record<"hybrid_rag" | "sql_rag", string> = {
  hybrid_rag: "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
  sql_rag: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
};

export function ChatMessage({ message }: { message: ChatMessageData }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-2xl rounded-2xl px-4 py-3 text-sm ${
          isUser
            ? "bg-blue-600 text-white"
            : message.isError
              ? "border border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
              : "border border-slate-200 bg-white text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
        }`}
      >
        {message.retrievalType && (
          <span
            className={`mb-2 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${RETRIEVAL_STYLE[message.retrievalType]}`}
          >
            {RETRIEVAL_LABEL[message.retrievalType]}
          </span>
        )}

        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>

        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 border-t border-slate-200 pt-2 dark:border-slate-700">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Sources</p>
            <ul className="space-y-1">
              {message.sources.map((source, i) => (
                <li key={i} className="text-xs text-slate-500 dark:text-slate-400">
                  {source.source_document} &gt; {source.section_title}{" "}
                  <span className="text-slate-400 dark:text-slate-500">({source.collection})</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
