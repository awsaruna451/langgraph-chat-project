const BASE_URL = "http://localhost:8000";

export async function sendMessage(threadId, message, userId) {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ thread_id: threadId, message, user_id: userId })
  });

  return res.json();
}

/**
 * Streams a chat response via SSE.
 *
 * @param {string} threadId
 * @param {string} message
 * @param {string} userId
 * @param {object} callbacks
 * @param {(content: string) => void} callbacks.onToken - called for each token chunk
 * @param {(tool: string, input: any) => void} [callbacks.onToolStart]
 * @param {(tool: string, output: any) => void} [callbacks.onToolEnd]
 * @param {() => void} [callbacks.onDone]
 * @param {(message: string) => void} [callbacks.onError]
 * @param {AbortSignal} [signal] - pass an AbortController.signal to allow cancellation
 */
export async function streamMessage(
  threadId,
  message,
  userId,
  { onToken, onToolStart, onToolEnd, onDone, onError },
  signal
) {
  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ thread_id: threadId, message, user_id: userId }),
    signal
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line
    const events = buffer.split("\n\n");
    buffer = events.pop(); // keep incomplete chunk for next read

    for (const rawEvent of events) {
      const line = rawEvent.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;

      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      const data = JSON.parse(jsonStr);

      switch (data.type) {
        case "token":
          onToken?.(data.content);
          break;
        case "tool_start":
          onToolStart?.(data.tool, data.input);
          break;
        case "tool_end":
          onToolEnd?.(data.tool, data.output);
          break;
        case "done":
          onDone?.();
          break;
        case "error":
          onError?.(data.message);
          break;
        default:
          break;
      }
    }
  }
}

export async function getConversation(threadId, userId) {
  const res = await fetch(`${BASE_URL}/conversation/${threadId}?user_id=${userId}`);
  return res.json();
}

export async function getConversations(userId) {
  const res = await fetch(`${BASE_URL}/conversations?user_id=${userId}`);
  return res.json();
}