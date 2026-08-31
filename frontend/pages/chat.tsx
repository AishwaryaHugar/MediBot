import { useState, useEffect, useRef, FormEvent } from "react";
import { useRouter } from "next/router";
import Head from "next/head";
import { sendChat } from "../lib/api";
import ChatMessage, { Message } from "../components/ChatMessage";

const COLLECTION_COLORS: Record<string, string> = {
  clinical:  "bg-blue-100   text-blue-700",
  nursing:   "bg-green-100  text-green-700",
  billing:   "bg-yellow-100 text-yellow-700",
  equipment: "bg-orange-100 text-orange-700",
  general:   "bg-gray-100   text-gray-600",
};

const ROLE_LABELS: Record<string, string> = {
  doctor:            "Doctor",
  nurse:             "Nurse",
  billing_executive: "Billing Executive",
  technician:        "Technician",
  admin:             "Admin",
};

const SAMPLE_PROMPTS: Record<string, string[]> = {
  doctor:            ["What is the first-line treatment for community-acquired pneumonia?", "What are the contraindications for metformin?", "Summarise the ICU handover nursing protocol."],
  nurse:             ["What is the infection control protocol for MRSA?", "Describe the ICU nursing assessment checklist.", "What is the policy on reporting a medication error?"],
  billing_executive: ["How many claims were escalated last month?", "What is the average approved amount by insurer?", "List all rejected claims from the Cardiology department."],
  technician:        ["How do I calibrate the MRI scanner?", "What is the maintenance schedule for the CT scanner?", "How do I reset a fault code on the ventilator?"],
  admin:             ["How many open maintenance tickets are there by category?", "What is the leave policy for ICU nursing staff?", "Summarise the billing codes for emergency procedures."],
};

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages]     = useState<Message[]>([]);
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const [token, setToken]           = useState("");
  const [role, setRole]             = useState("");
  const [username, setUsername]     = useState("");
  const [collections, setCollections] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t  = localStorage.getItem("medibot_token");
    const r  = localStorage.getItem("medibot_role");
    const u  = localStorage.getItem("medibot_username");
    const c  = localStorage.getItem("medibot_collections");
    if (!t || !r) { router.push("/"); return; }
    setToken(t);
    setRole(r);
    setUsername(u || "");
    setCollections(c ? JSON.parse(c) : []);
    setMessages([{
      role: "assistant",
      content: `Hello! I'm MediBot, your knowledge assistant for MediAssist Health Network. You're signed in as ${ROLE_LABELS[r] || r}. How can I help you today?`,
    }]);
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    try {
      const res = await sendChat(question, token);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, response: res },
      ]);
    } catch (err: unknown) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Error: ${err instanceof Error ? err.message : "Request failed"}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.clear();
    router.push("/");
  }

  const prompts = SAMPLE_PROMPTS[role] || [];

  return (
    <>
      <Head><title>MediBot — Chat</title></Head>
      <div className="flex h-screen bg-gray-50 overflow-hidden">

        {/* Sidebar */}
        <aside className="w-72 bg-white border-r border-gray-200 flex flex-col shrink-0">
          {/* Brand */}
          <div className="p-5 border-b border-gray-100">
            <div className="flex items-center gap-2.5 mb-3">
              <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">M</div>
              <span className="font-bold text-gray-900">MediBot</span>
            </div>
            <div className="bg-brand-50 rounded-lg px-3 py-2 text-sm">
              <p className="text-gray-500 text-xs">Signed in as</p>
              <p className="font-semibold text-brand-700">{ROLE_LABELS[role] || role}</p>
              <p className="text-gray-400 text-xs font-mono">{username}</p>
            </div>
          </div>

          {/* Collections */}
          <div className="p-5 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Accessible Collections</p>
            <div className="flex flex-wrap gap-1.5">
              {collections.map((c) => (
                <span key={c} className={`text-xs px-2.5 py-1 rounded-full font-medium ${COLLECTION_COLORS[c] ?? "bg-gray-100 text-gray-600"}`}>
                  {c}
                </span>
              ))}
            </div>
          </div>

          {/* Sample prompts */}
          <div className="p-5 flex-1 overflow-y-auto">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Sample Questions</p>
            <div className="space-y-2">
              {prompts.map((p, i) => (
                <button
                  key={i}
                  onClick={() => setInput(p)}
                  className="w-full text-left text-xs text-gray-600 bg-gray-50 hover:bg-brand-50 hover:text-brand-700 rounded-lg px-3 py-2.5 transition-colors border border-transparent hover:border-brand-200"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Logout */}
          <div className="p-4 border-t border-gray-100">
            <button
              onClick={logout}
              className="w-full text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg py-2 transition-colors"
            >
              Sign out
            </button>
          </div>
        </aside>

        {/* Main chat area */}
        <div className="flex flex-col flex-1 min-w-0">
          {/* Header */}
          <header className="bg-white border-b border-gray-200 px-6 py-3.5 flex items-center justify-between shrink-0">
            <div>
              <h1 className="font-semibold text-gray-900 text-sm">MediAssist Knowledge Assistant</h1>
              <p className="text-xs text-gray-400">Answers are grounded in your organisation's documents</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-400 rounded-full"></span>
              <span className="text-xs text-gray-400">Online</span>
            </div>
          </header>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-6 chat-scroll">
            {messages.map((msg, i) => (
              <ChatMessage key={i} message={msg} />
            ))}

            {loading && (
              <div className="flex justify-start mb-4">
                <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                  <div className="flex gap-1 items-center h-4">
                    <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="bg-white border-t border-gray-200 px-6 py-4 shrink-0">
            <form onSubmit={handleSubmit} className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
                placeholder="Ask about protocols, billing codes, equipment guides…"
                className="flex-1 px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="px-5 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-xl text-sm font-medium transition-colors"
              >
                Send
              </button>
            </form>
          </div>
        </div>

      </div>
    </>
  );
}
