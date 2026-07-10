// SSE helpers. Jobs use a GET stream (EventSource); chat is a POST multipart
// stream (fetch + ReadableStream, since EventSource can't POST).

export interface JobStreamHandlers {
  onProgress?: (data: { progress: number; message: string; stats?: unknown }) => void;
  onDone?: (data: { result: unknown }) => void;
  onFailed?: (data: { error: string }) => void;
}

/** Subscribe to a job's progress stream. Returns an unsubscribe function. */
export function subscribeJob(jobId: string, handlers: JobStreamHandlers): () => void {
  const es = new EventSource(`/api/jobs/${jobId}/events`);
  es.addEventListener("progress", (e) => handlers.onProgress?.(JSON.parse((e as MessageEvent).data)));
  es.addEventListener("done", (e) => {
    handlers.onDone?.(JSON.parse((e as MessageEvent).data));
    es.close();
  });
  es.addEventListener("failed", (e) => {
    handlers.onFailed?.(JSON.parse((e as MessageEvent).data));
    es.close();
  });
  es.onerror = () => es.close();
  return () => es.close();
}

export type ChatEvent =
  | { event: "message_created"; data: { user_message_id: number; assistant_message_id: number } }
  | { event: "token"; data: { text: string } }
  | { event: "tool_use"; data: { name: string; summary: string } }
  | {
      event: "pending_change";
      data: { change_id: number; module: string; summary: string; diff: unknown };
    }
  | { event: "done"; data: { message_id: number } }
  | { event: "error"; data: { message: string } };

/** POST a chat message and yield parsed SSE events as they stream in. */
export async function* streamChat(
  threadId: number,
  content: string,
  files: File[] = [],
): AsyncGenerator<ChatEvent> {
  const form = new FormData();
  form.set("content", content);
  for (const f of files) form.append("files", f);

  const res = await fetch(`/api/chat/threads/${threadId}/messages`, {
    method: "POST",
    body: form,
  });
  if (!res.ok || !res.body) {
    throw new Error(`chat stream failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE frames are separated by a blank line.
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const ev = parseFrame(frame);
      if (ev) yield ev;
    }
  }
}

function parseFrame(frame: string): ChatEvent | null {
  let event = "";
  let dataLine = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
  }
  if (!event || !dataLine) return null;
  try {
    return { event, data: JSON.parse(dataLine) } as ChatEvent;
  } catch {
    return null;
  }
}
