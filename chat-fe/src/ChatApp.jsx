import { useState, useEffect, useRef } from "react";
import { useChat } from "./hook/useChat";
import "./ChatApp.css";

function formatThreadLabel(id) {
  return `Thread ${id.slice(0, 8)}`;
}

export default function ChatApp() {
  const {userId, threads, threadId,  messages, loading, error, send, newChat, loadChat,clearError } =
    useChat();

  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    send(text);
    setInput("");
    inputRef.current?.focus();
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div className="chat-layout">
      {/* ── Sidebar ─────────────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-header">

          <button className="new-chat-btn" onClick={newChat} title="New chat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New chat
          </button>
        </div>

        <nav className="thread-list" aria-label="Conversation history">
          {threads.length === 0 && (
            <p className="thread-empty">No conversations yet.</p>
          )}
          {[...threads].reverse().map((id) => (
            <button
              key={id}
              className={`thread-item${id === threadId ? " thread-item--active" : ""}`}
              onClick={() => loadChat(id)}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              {formatThreadLabel(id)}
            </button>
          ))}
        </nav>

      </aside>

      {/* ── Main ────────────────────────────────────────── */}
      <main className="chat-main">
        {/* Message feed */}
        <section className="message-feed" aria-label="Messages" aria-live="polite">
          {isEmpty && !loading && (
            <div className="empty-state">
              <div className="empty-icon" aria-hidden="true">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <h2 className="empty-heading">Start a conversation</h2>
              <p className="empty-sub">Type a message below to begin.</p>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`message message--${m.role}`}>
              <span className="message-role">
                {m.role === "human" ? "You" : "Assistant"}
              </span>
              <p className="message-content">{m.content}</p>
            </div>
          ))}

          {loading && (
            <div className="message message--assistant message--typing">
              <span className="message-role">Assistant</span>
              <span className="typing-indicator" aria-label="Typing">
                <span /><span /><span />
              </span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </section>

        {/* Error banner */}
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button className="error-dismiss" onClick={clearError} aria-label="Dismiss error">✕</button>
          </div>
        )}

        {/* Input row */}
        <div className="input-row">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message…"
            rows={1}
            aria-label="Message input"
            disabled={loading}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={!input.trim() || loading}
            aria-label="Send message"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </main>
    </div>
  );
}
