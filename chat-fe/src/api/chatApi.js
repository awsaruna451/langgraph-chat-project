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

export async function getConversation(threadId, userId) {
  const res = await fetch(`${BASE_URL}/conversation/${threadId}?user_id=${userId}`);
  return res.json();
}

export async function getConversations(userId) {
  const res = await fetch(`${BASE_URL}/conversations?user_id=${userId}`);
  return res.json();
}