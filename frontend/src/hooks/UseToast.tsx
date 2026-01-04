import {
  CheckmarkOutline,
  Information,
  Warning,
  WarningAltFilled,
} from "@carbon/icons-react";
import { Theme, useTheme } from "@mui/material/styles";
import { useMemo } from "react";
import {
  Id,
  ToastContent,
  ToastOptions,
  TypeOptions,
  UpdateOptions,
  toast,
} from "react-toastify";
import type { IconProps as ToastifyIconProps } from "react-toastify";

export type Toast = {
  info: (content: ToastContent, options?: ToastOptions) => Id;
  success: (content: ToastContent, options?: ToastOptions) => Id;
  warning: (content: ToastContent, options?: ToastOptions) => Id;
  error: (content: ToastContent, options?: ToastOptions) => Id;
  dismiss: (id?: string | number | undefined) => void;
  update: (id: string | number, options: UpdateOptions) => void;
};

function ToastIcon({ type }: { type: TypeOptions }) {
  switch (type) {
    case "info":
      return <Information size={20} />;
    case "error":
      return <Warning size={20} />;
    case "success":
      return <CheckmarkOutline size={20} />;
    case "warning":
      return <WarningAltFilled size={20} />;
    default:
      return null;
  }
}

const defaultToastOptions = (theme: Theme): ToastOptions => ({
  style: {
    fontWeight: "500 !important",
    fontSize: "0.875rem",
    lineHeight: 1.43,
    letterSpacing: "0.01071em",
    borderRadius: theme.shape.borderRadius,
  },
  icon: ({ type }: ToastifyIconProps) => <ToastIcon type={type} />,
});

export const toastIds = {
  websocketConnecting: "websocketConnecting",
  websocketConnectionLost: "websocketConnectionLost",
  websocketSubscriptionResultError: "websocketSubscriptionResultError",
  sessionExpired: "sessionExpired",
  userLoadError: "userLoadError",
};

export const useToast = (): Toast => {
  const localTheme = useTheme();
  return useMemo(
    () => ({
      info: (content: ToastContent, options: ToastOptions = {}) => {
        const mergedOptions = {
          ...defaultToastOptions(localTheme),
          ...options,
        };
        return toast.info(content, mergedOptions);
      },
      success: (content: ToastContent, options: ToastOptions = {}) => {
        const mergedOptions = {
          ...defaultToastOptions(localTheme),
          ...options,
        };
        return toast.success(content, mergedOptions);
      },
      warning: (content: ToastContent, options: ToastOptions = {}) => {
        const mergedOptions = {
          ...defaultToastOptions(localTheme),
          ...options,
        };
        return toast.warning(content, mergedOptions);
      },
      error: (content: ToastContent, options: ToastOptions = {}) => {
        const mergedOptions = {
          ...defaultToastOptions(localTheme),
          ...options,
        };
        return toast.error(content, mergedOptions);
      },
      dismiss: (id: string | number | undefined = undefined) =>
        toast.dismiss(id),
      update: (id: string | number, options: UpdateOptions) =>
        toast.update(id, options),
    }),
    [localTheme],
  );
};
