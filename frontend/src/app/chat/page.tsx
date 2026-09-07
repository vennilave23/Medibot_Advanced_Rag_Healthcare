"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/contexts/SessionContext";
import { chat as chatRequest, getCollections } from "@/lib/api";
import { ChatMessage, type ChatMessageData } from "@/components/ChatMessage";
import { Sidebar } from "@/components/Sidebar";

export default function ChatPage() {
  const router = useRouter();
  const { session, isLoading, logout } = useSession();

  const [collections, setCollections] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [question, setQuestion] = useState("");
  const [isSending, setIsSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoading && !session) {
      router.replace("/");
    }
  }, [isLoading, session, router]);

  useEffect(() => {
    if (!session) return;
    getCollections(session.role)
      .then((res) => setCollections(res.collections))
      .catch(() => setCollections([]));
  }, [session]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (isLoading || !session) {
    return <div className="flex flex-1 items-center justify-center text-sm text-slate-400">Loading...</div>;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isSending || !session) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setQuestion("");
    setIsSending(true);

    try {
      const res = await chatRequest(trimmed, session.role);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, sources: res.sources, retrievalType: res.retrieval_type },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "Something went wrong. Please try again.",
          isError: true,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  function handleLogout() {
    logout();
    router.push("/");
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      <Sidebar username={session.username} role={session.role} collections={collections} onLogout={handleLogout} />

      <div className="flex flex-1 flex-col bg-slate-50 dark:bg-slate-950">
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.length === 0 && (
            <p className="text-center text-sm text-slate-400">
              Ask a question about your accessible document collections, or an analytics question if you have
              access.
            </p>
          )}
          {messages.map((message, i) => (
            <ChatMessage key={i} message={message} />
          ))}
          {isSending && <p className="text-xs text-slate-400">MediBot is thinking...</p>}
          <div ref={bottomRef} />
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex gap-2 border-t border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask MediBot a question..."
            disabled={isSending}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-50"
          />
          <button
            type="submit"
            disabled={isSending || !question.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
