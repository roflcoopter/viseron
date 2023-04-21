import ErrorOutlineOutlinedIcon from "@mui/icons-material/ErrorOutlineOutlined";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import ReportProblemOutlined from "@mui/icons-material/ReportProblemOutlined";
import TaskAltOutlinedIcon from "@mui/icons-material/TaskAltOutlined";
import { Theme, useTheme } from "@mui/material/styles";
import { ToastContent, ToastOptions, toast } from "react-toastify";

export type Toast = {
  info: (content: ToastContent, options?: ToastOptions) => React.ReactText;
  success: (content: ToastContent, options?: ToastOptions) => React.ReactText;
  warning: (content: ToastContent, options?: ToastOptions) => React.ReactText;
  error: (content: ToastContent, options?: ToastOptions) => React.ReactText;
  dismiss: (id?: string | number | undefined) => void;
};

const defaultToastOptions = (theme: Theme) => ({
  style: {
    fontWeight: "500 !important",
    fontSize: "0.875rem",
    lineHeight: 1.43,
    letterSpacing: "0.01071em",
    border: `1px solid ${theme.palette.divider}`,
    borderRadius: theme.shape.borderRadius,
  },
});

export const toastIds = {
  websocketConnecting: "websocketConnecting",
  websocketConnectionLost: "websocketConnectionLost",
  sessionExpired: "sessionExpired",
  userLoadError: "userLoadError",
};

export const useToast = () => {
  const theme = useTheme();
  return {
    info: (content: ToastContent, options: ToastOptions = {}) => {
      options = { ...defaultToastOptions(theme), ...options };
      return toast.info(content, {
        ...options,
        icon: <InfoOutlinedIcon />,
      });
    },
    success: (content: ToastContent, options: ToastOptions = {}) => {
      options = { ...defaultToastOptions(theme), ...options };
      return toast.success(content, {
        ...options,
        icon: <TaskAltOutlinedIcon />,
      });
    },
    warning: (content: ToastContent, options: ToastOptions = {}) => {
      options = { ...defaultToastOptions(theme), ...options };
      return toast.warning(content, {
        ...options,
        icon: <ReportProblemOutlined />,
      });
    },
    error: (content: ToastContent, options: ToastOptions = {}) => {
      options = { ...defaultToastOptions(theme), ...options };
      return toast.error(content, {
        ...options,
        icon: <ErrorOutlineOutlinedIcon />,
      });
    },
    dismiss: (id: string | number | undefined = undefined) => toast.dismiss(id),
  };
};
