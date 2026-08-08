import { useState, useEffect, useCallback, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { streamMessage, getConversation, getConversations } from "../api/chatApi";

const USER_ID_KEY = "chat_user_id";
const THREAD_ID_KEY = "chat_thread_id";

function getOrCreateUserId() {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = 'alex';
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

function getOrCreateThreadId() {
  let id = localStorage.getItem(THREAD_ID_KEY);
  if (!id) {
    id = uuidv4();
    localStorage.setItem(THREAD_ID_KEY, id);
  }
  return id;
}

export function useChat() {
  const [userId] = useState(getOrCreateUserId);
  const [threadId, setThreadId] = useState(getOrCreateThreadId);
  const [threads, setThreads] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  useEffect(() => {
    loadThreads();
    restoreConversation(threadId); // ← load the last active thread's messages
  }, []);

  async function loadThreads() {
    try {
      const data = await getConversations(userId);
      setThreads(data.conversations ?? data ?? []);
    } catch (err) {
      console.error("Failed to load threads:", err);
    }
  }

  async function restoreConversation(id) {
    try {
      const history = await getConversation(id, userId);
      setMessages(history ?? []);
    } catch (err) {
      // thread might not exist yet (e.g. brand new user) — safe to ignore
      console.warn("No existing conversation for thread:", id);
    }
  }

  function addThread(id) {
    setThreads((prev) => (prev.includes(id) ? prev : [...prev, id]));
  }

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    const id = uuidv4();
    localStorage.setItem(THREAD_ID_KEY, id);
    setThreadId(id);
    setMessages([]);
    setError(null);
    setLoading(false);
  }, []);

  const loadChat = useCallback(async (id) => {
    abortRef.current?.abort();
    setError(null);
    try {
      const history = await getConversation(id, userId);
      localStorage.setItem(THREAD_ID_KEY, id);
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

      const aiMsgIndex = { current: null };
      setMessages((prev) => {
        aiMsgIndex.current = prev.length;
        return [...prev, { role: "ai", content: "" }];
      });

      setLoading(true);
      setError(null);
      addThread(threadId);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamMessage(
          threadId,
          trimmed,
          userId,
          {
            onToken: (content) => {
              setMessages((prev) => {
                const updated = [...prev];
                const idx = aiMsgIndex.current;
                updated[idx] = {
                  ...updated[idx],
                  content: updated[idx].content + content,
                };
                return updated;
              });
            },

            onDone: () => {
              setLoading(false);
       
            },
            onError: (message) => {
              setError(message || "Something went wrong while streaming.");
              setLoading(false);
            },
          },
          controller.signal
        );
      } catch (err) {
        if (err.name !== "AbortError") {
          setError("Failed to send message. Please try again.");
          setMessages((prev) => prev.slice(0, -2));
        }
      } finally {
        setLoading(false);
      }
    },
    [threadId, userId, loading]
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setLoading(false);
  }, []);

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
    stop,
    clearError,
  };
}