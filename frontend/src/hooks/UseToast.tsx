import ErrorOutlineOutlinedIcon from "@mui/icons-material/ErrorOutlineOutlined";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import ReportProblemOutlined from "@mui/icons-material/ReportProblemOutlined";
import TaskAltOutlinedIcon from "@mui/icons-material/TaskAltOutlined";
import { Theme, useTheme } from "@mui/material/styles";
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
      return <InfoOutlinedIcon />;
    case "error":
      return <ErrorOutlineOutlinedIcon />;
    case "success":
      return <TaskAltOutlinedIcon />;
    case "warning":
      return <ReportProblemOutlined />;
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
    border: `1px solid ${theme.palette.divider}`,
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

export const useToast = () => {
  const localTheme = useTheme();
  return {
    info: (content: ToastContent, options: ToastOptions = {}) => {
      options = { ...defaultToastOptions(localTheme), ...options };
      return toast.info(content, options);
    },
    success: (content: ToastContent, options: ToastOptions = {}) => {
      options = { ...defaultToastOptions(localTheme), ...options };
      return toast.success(content, options);
    },
    warning: (content: ToastContent, options: ToastOptions = {}) => {
      options = { ...defaultToastOptions(localTheme), ...options };
      return toast.warning(content, options);
    },
    error: (content: ToastContent, options: ToastOptions = {}) => {
      options = { ...defaultToastOptions(localTheme), ...options };
      return toast.error(content, options);
    },
    dismiss: (id: string | number | undefined = undefined) => toast.dismiss(id),
    update: (id: string | number, options: UpdateOptions) =>
      toast.update(id, options),
  };
};
