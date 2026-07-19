import { useState, useEffect, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { sendMessage, getConversation, getConversations } from "../api/chatApi";

const USER_ID_KEY = "chat_user_id";


function getOrCreateUserId() {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = 'alex';
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}
/**
 * Core chat state and actions.
 *
 * @returns {{
 *   threadId: string,
 *   threads: string[],
 *   messages: Array<{ role: string, content: string }>,
 *   loading: boolean,
 *   error: string | null,
 *   newChat: () => void,
 *   loadChat: (id: string) => Promise<void>,
 *   send: (text: string) => Promise<void>,
 *   clearError: () => void,
 * }}
 */
export function useChat() {
  const [userId] = useState(getOrCreateUserId);
  const [threadId, setThreadId] = useState(() => uuidv4());
  const [threads, setThreads] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadThreads();
  }, []);

  async function loadThreads() {
    try {
      const data = await getConversations(userId);
      setThreads(data.conversations ?? data ?? []);
    } catch (err) {
      console.error("Failed to load threads:", err);
    }
  }

  function addThread(id) {
    setThreads((prev) => (prev.includes(id) ? prev : [...prev, id]));
  }

  const newChat = useCallback(() => {
    setThreadId(uuidv4());
    setMessages([]);
    setError(null);
  }, []);

  const loadChat = useCallback(async (id) => {
    setError(null);
    try {
      const history = await getConversation(id, userId);
      setThreadId(id);
      setMessages(history);
    } catch (err) {
      setError("Failed to load conversation. Please try again.");
    }
  }, []);

  const send = useCallback(
    async (userText) => {
      const trimmed = userText.trim();
      if (!trimmed || loading) return;

      const userMsg = { role: "human", content: trimmed };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);
      setError(null);
      addThread(threadId);

      try {
        const res = await sendMessage(threadId, trimmed, userId);
        setMessages((prev) => [
          ...prev,
          { role: "ai", content: res.response },
        ]);
      } catch (err) {
        setError("Failed to send message. Please try again.");
        setMessages((prev) => prev.slice(0, -1));
      } finally {
        setLoading(false);
      }
    },
    [threadId, loading]
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    threadId,
    threads,
    messages,
    loading,
    error,
    newChat,
    loadChat,
    send,
    clearError,
  };
}
