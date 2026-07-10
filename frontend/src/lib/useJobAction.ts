import { useState } from "react";
import { subscribeJob } from "./sse";

/** Fire a job-kickoff request, subscribe to its SSE progress, and surface
 * busy/message/error state — shared by any button that submits an async job
 * (evaluate, generate/export document, research company, ...). */
export function useJobAction(onDone?: () => void) {
  const [state, setState] = useState<{ busy: boolean; message?: string; error?: string }>({ busy: false });
  const run = (submit: () => Promise<{ job_id: string }>) => {
    setState({ busy: true, message: "starting…" });
    submit()
      .then(({ job_id }) => {
        subscribeJob(job_id, {
          onProgress: (d) => setState({ busy: true, message: d.message }),
          onDone: () => {
            setState({ busy: false, message: undefined });
            onDone?.();
          },
          onFailed: (d) => setState({ busy: false, error: d.error }),
        });
      })
      .catch((err) => setState({ busy: false, error: err instanceof Error ? err.message : String(err) }));
  };
  return { ...state, run };
}
