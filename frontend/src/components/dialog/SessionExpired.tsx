import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import queryClient from "lib/api/client";
import { clearSessionExpiredTimeout } from "lib/tokens";

const useSessionExpiredEvent = (
  setOpen: React.Dispatch<React.SetStateAction<boolean>>,
) => {
  const navigate = useNavigate();

  useEffect(() => {
    const handleSessionExpired = () => {
      queryClient.removeQueries({
        predicate(query) {
          return (
            query.queryKey[0] !== "auth" && query.queryKey[1] !== "enabled"
          );
        },
      });
      queryClient.invalidateQueries({
        predicate(query) {
          return (
            query.queryKey[0] !== "auth" && query.queryKey[1] !== "enabled"
          );
        },
      });
      navigate("/login", { replace: true });
      setOpen(true);
    };

    document.addEventListener("session-expired", handleSessionExpired);

    return () => {
      document.removeEventListener("session-expired", handleSessionExpired);
      clearSessionExpiredTimeout();
    };
  }, [navigate, setOpen]);
};

function SessionExpired() {
  const [open, setOpen] = useState(false);
  useSessionExpiredEvent(setOpen);

  return (
    <Dialog
      open={open}
      onClose={() => {
        setOpen(false);
      }}
      aria-labelledby="alert-dialog-title"
      aria-describedby="alert-dialog-description"
    >
      <DialogTitle id="alert-dialog-title">Session expired</DialogTitle>
      <DialogContent>
        <DialogContentText id="alert-dialog-description">
          Your session has expired. Please log in again.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={() => {
            setOpen(false);
          }}
        >
          OK
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default SessionExpired;
