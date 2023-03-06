import CloseIcon from "@mui/icons-material/Close";
import MuiAlert, { AlertColor, AlertProps } from "@mui/material/Alert";
import IconButton from "@mui/material/IconButton";
import Snackbar from "@mui/material/Snackbar";
import React, { createContext, useContext } from "react";

const Alert = React.forwardRef<HTMLDivElement, AlertProps>((props, ref) => (
  <MuiAlert elevation={6} ref={ref} variant="filled" {...props} />
));

export type SnackbarContextActions = {
  showSnackbar: (
    message: string,
    severity: AlertColor,
    autoHideDuration?: number | undefined
  ) => void;
};

const SnackbarContext = createContext({} as SnackbarContextActions);

interface SnackbarContextProviderProps {
  children: React.ReactNode;
}

const SnackbarProvider: React.FC<SnackbarContextProviderProps> = ({
  children,
}) => {
  const [open, setOpen] = React.useState<boolean>(false);
  const [message, setMessage] = React.useState<string>("");
  const [severity, setSeverity] = React.useState<AlertColor>("success");
  const [autoHideDuration, setAutoHideDuration] = React.useState<number>(5000);

  const showSnackbar = (
    _message: string,
    _severity: AlertColor,
    _autoHideDuration = 5000
  ) => {
    setMessage(_message);
    setSeverity(_severity);
    setAutoHideDuration(_autoHideDuration);
    setOpen(true);
  };

  const handleClose = (
    _event: React.SyntheticEvent | Event,
    reason?: string
  ) => {
    if (reason === "clickaway") {
      return;
    }

    setOpen(false);
  };

  const action = (
    <React.Fragment>
      <IconButton
        size="small"
        aria-label="close"
        color="inherit"
        onClick={handleClose}
      >
        <CloseIcon fontSize="small" />
      </IconButton>
    </React.Fragment>
  );

  return (
    <SnackbarContext.Provider value={{ showSnackbar }}>
      <Snackbar
        open={open}
        autoHideDuration={autoHideDuration}
        onClose={handleClose}
        action={action}
      >
        <Alert onClose={handleClose} severity={severity}>
          {message}
        </Alert>
      </Snackbar>
      {children}
    </SnackbarContext.Provider>
  );
};

const useSnackbar = (): SnackbarContextActions => {
  const context = useContext(SnackbarContext);

  if (!context) {
    throw new Error("useSnackbar must be used within an SnackbarProvider");
  }

  return context;
};

export { SnackbarProvider, useSnackbar };
