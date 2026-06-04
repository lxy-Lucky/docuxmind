/**
 * POST a JSON body to an SSE endpoint and stream `event: ... data: ...` frames.
 * EventSource doesn't support POST, so we use fetch + ReadableStream and parse
 * the SSE wire format manually.
 */
export interface SSEHandler {
  onEvent: (event: string, data: any) => void;
  onError?: (err: unknown) => void;
  onDone?: () => void;
}

export interface SSESession {
  promise: Promise<void>;
  abort: () => void;
}

export function streamSSE(
  url: string,
  body: unknown,
  handler: SSEHandler,
): SSESession {
  const ctrl = new AbortController();

  const promise = (async () => {
    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
    } catch (e) {
      handler.onError?.(e);
      return;
    }
    if (!res.ok || !res.body) {
      handler.onError?.(new Error(`${res.status} ${res.statusText}`));
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        let sep = buf.indexOf("\n\n");
        while (sep !== -1) {
          const frame = buf.slice(0, sep);
          buf = buf.slice(sep + 2);
          parseFrame(frame, handler);
          sep = buf.indexOf("\n\n");
        }
      }
      // tail
      if (buf.trim()) parseFrame(buf, handler);
      handler.onDone?.();
    } catch (e) {
      if ((e as any)?.name !== "AbortError") handler.onError?.(e);
    } finally {
      try { reader.releaseLock(); } catch {}
    }
  })();

  return { promise, abort: () => ctrl.abort() };
}

function parseFrame(frame: string, handler: SSEHandler) {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!dataLines.length) return;
  const raw = dataLines.join("\n");
  let data: unknown = raw;
  try {
    data = JSON.parse(raw);
  } catch {
    /* keep as string */
  }
  handler.onEvent(event, data);
}
