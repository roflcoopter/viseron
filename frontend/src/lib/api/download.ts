import { Id, toast } from "react-toastify";

import { viseronAPI } from "lib/api/client";
import * as types from "lib/types";

export const downloadFile = async (
  message: types.DownloadFileResponse,
  toastId: Id,
  cameraName: string,
) => {
  toast.info(`${cameraName}: Downloading file...`, {
    toastId,
    autoClose: false,
  });
  try {
    const response = await viseronAPI.get(`download?token=${message.token}`, {
      responseType: "blob",
      onDownloadProgress: (progressEvent) => {
        if (progressEvent.progress) {
          if (progressEvent.progress === 1) {
            toast.update(toastId, {
              type: "success",
              render: `${cameraName}: Download complete!`,
              autoClose: 5000,
            });
          } else {
            const percentCompleted = Math.round(progressEvent.progress * 100);
            toast.update(toastId, {
              render: `${cameraName}: Downloading file... ${percentCompleted}%`,
            });
          }
        }
      },
    });

    const blob = new Blob([response.data], {
      type: response.headers["content-type"],
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute(
      "download",
      message.filename.split("/").pop() || "download",
    );
    document.body.appendChild(link);
    link.click();

    // Cleanup
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    toast.update(toastId, {
      type: "error",
      render: `${cameraName}: Download failed: ${error}`,
      autoClose: 5000,
    });
  }
};
