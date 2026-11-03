import { useCallback, useContext, useRef, useState } from "react";
import { toast } from "react-toastify";

import { ViseronContext } from "context/ViseronContext";
import { downloadFile } from "lib/api/download";
import { commandErrorMessage, renderTimelapse } from "lib/commands";
import { getCameraNameFromQueryCache } from "lib/helpers";
import { RenderTimelapseParams } from "lib/messages";
import * as types from "lib/types";
import { SubscriptionUnsubscribe } from "lib/websockets";

export type RenderTimelapseState =
  | { status: "idle" }
  | { status: "starting" }
  | { status: "queued" }
  | {
      status: "rendering";
      frame: number;
      total_frames: number;
      progress: number;
    }
  | { status: "encoding" }
  | { status: "downloading" }
  | { status: "done" }
  | { status: "error"; error: string }
  | { status: "cancelled" };

type FinalState = Extract<
  RenderTimelapseState,
  { status: "done" | "error" | "cancelled" }
>;

export const isRenderActive = (state: RenderTimelapseState) =>
  ["starting", "queued", "rendering", "encoding", "downloading"].includes(
    state.status,
  );

const toastText = (cameraName: string, state: RenderTimelapseState) => {
  switch (state.status) {
    case "starting":
      return `${cameraName}: Starting timelapse render...`;
    case "queued":
      return `${cameraName}: Timelapse render queued...`;
    case "rendering":
      return `${cameraName}: Rendering timelapse... ${Math.round(state.progress)}%`;
    case "encoding":
      return `${cameraName}: Encoding timelapse...`;
    case "done":
      return `${cameraName}: Timelapse downloaded`;
    case "error":
      return `${cameraName}: Timelapse render failed: ${state.error}`;
    default:
      return null;
  }
};

export const useRenderTimelapse = () => {
  const { connection } = useContext(ViseronContext);
  const [state, setState] = useState<RenderTimelapseState>({ status: "idle" });
  const stateRef = useRef<RenderTimelapseState>({ status: "idle" });
  const activeRef = useRef(false);
  const cancelRef = useRef<SubscriptionUnsubscribe | null>(null);
  const cancelRequestedRef = useRef(false);
  const hiddenRef = useRef(false);
  const toastIdRef = useRef("");
  const cameraNameRef = useRef("");

  // Progress is shown in a toast while hidden. The toast is driven from the
  // status callbacks so that it keeps updating after the page unmounts.
  const syncToast = useCallback((next: RenderTimelapseState) => {
    const toastId = toastIdRef.current;
    if (next.status === "cancelled") {
      toast.dismiss(toastId);
      return;
    }
    // downloadFile shows the download progress in the same toast
    const text = toastText(cameraNameRef.current, next);
    if (text === null) {
      return;
    }
    let options;
    if (next.status === "error") {
      options = { type: "error" as const, autoClose: 5000 };
    } else if (next.status === "done") {
      options = { type: "success" as const, autoClose: 5000 };
    } else {
      options = { type: "info" as const, autoClose: false as const };
    }
    if (toast.isActive(toastId)) {
      toast.update(toastId, { render: text, ...options });
    } else {
      toast(text, { toastId, ...options });
    }
  }, []);

  const update = useCallback(
    (next: RenderTimelapseState) => {
      stateRef.current = next;
      setState(next);
      if (hiddenRef.current) {
        syncToast(next);
      }
    },
    [syncToast],
  );

  const finish = useCallback(
    (next: FinalState) => {
      activeRef.current = false;
      cancelRef.current = null;
      update(next);
    },
    [update],
  );

  const cancelRender = useCallback(async () => {
    const cancel = cancelRef.current;
    if (!cancel) {
      return;
    }
    // Finish first so that status messages sent before the cancel are ignored
    finish({ status: "cancelled" });
    await cancel();
  }, [finish]);

  const start = useCallback(
    async (params: RenderTimelapseParams) => {
      if (activeRef.current) {
        return;
      }
      activeRef.current = true;
      cancelRequestedRef.current = false;
      hiddenRef.current = false;
      toastIdRef.current = `timelapse-render-${params.camera_identifier}-${Date.now()}`;
      cameraNameRef.current = getCameraNameFromQueryCache(
        params.camera_identifier,
      );
      update({ status: "starting" });

      if (!connection) {
        finish({ status: "error", error: "Not connected" });
        return;
      }

      const toastId = toastIdRef.current;
      const onStatus = async (status: types.TimelapseRenderStatus) => {
        if (!activeRef.current) {
          return;
        }
        if (status.status !== "done") {
          update(status);
          return;
        }
        update({ status: "downloading" });
        const downloaded = await downloadFile(
          status,
          toastId,
          cameraNameRef.current,
        );
        finish(
          downloaded
            ? { status: "done" }
            : { status: "error", error: "Download failed" },
        );
      };
      const onError = (message: types.WebSocketSubscriptionErrorResponse) => {
        if (activeRef.current) {
          finish({ status: "error", error: message.error.message });
        }
      };

      try {
        cancelRef.current = await renderTimelapse(
          connection,
          params,
          onStatus,
          onError,
        );
      } catch (error) {
        finish({ status: "error", error: commandErrorMessage(error) });
        return;
      }
      if (cancelRequestedRef.current) {
        await cancelRender();
      }
    },
    [connection, update, finish, cancelRender],
  );

  const cancel = useCallback(async () => {
    // The file is already on its way to the browser
    if (!activeRef.current || stateRef.current.status === "downloading") {
      return;
    }
    if (!cancelRef.current) {
      // Not acknowledged by the server yet, cancel as soon as it is
      cancelRequestedRef.current = true;
      return;
    }
    await cancelRender();
  }, [cancelRender]);

  const reset = useCallback(() => {
    if (!activeRef.current) {
      update({ status: "idle" });
    }
  }, [update]);

  // Move the progress of a running render into a toast
  const hide = useCallback(() => {
    if (!activeRef.current || hiddenRef.current) {
      return;
    }
    hiddenRef.current = true;
    syncToast(stateRef.current);
  }, [syncToast]);

  const show = useCallback(() => {
    if (!hiddenRef.current) {
      return;
    }
    hiddenRef.current = false;
    if (stateRef.current.status !== "downloading") {
      toast.dismiss(toastIdRef.current);
    }
  }, []);

  return { state, start, cancel, reset, hide, show };
};
