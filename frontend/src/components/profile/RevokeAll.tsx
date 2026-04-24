import { TrashCan } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useProfileRevokeAll } from "lib/api/profile";

function ConfirmRevokeAllDialog({
  open,
  onConfirm,
  onClose,
  isPending,
}: {
  open: boolean;
  onConfirm: () => void;
  onClose: () => void;
  isPending: boolean;
}) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm">
      <DialogTitle>Revoke all sessions and tokens?</DialogTitle>
      <DialogContent>
        <DialogContentText>
          This will immediately invalidate <strong>all active sessions</strong>{" "}
          (on every device) and <strong>all personal access tokens</strong>. You
          will be logged out after confirming. This action cannot be undone.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isPending}>
          Cancel
        </Button>
        <Button
          variant="contained"
          color="error"
          onClick={onConfirm}
          loading={isPending}
          startIcon={<TrashCan />}
        >
          Revoke all
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export function RevokeAll() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const revokeAll = useProfileRevokeAll();
  const navigate = useNavigate();

  const handleConfirm = () => {
    revokeAll.mutate(undefined, {
      onSuccess: () => navigate("/login"),
    });
  };

  return (
    <Box>
      <Typography variant="subtitle2" color="error" sx={{ marginBottom: 0.5 }}>
        Danger zone
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ marginBottom: 1.5 }}
      >
        Revoke all active sessions on every device and all personal access
        tokens. You will be logged out immediately.
      </Typography>
      <Button
        variant="outlined"
        color="error"
        startIcon={<TrashCan />}
        onClick={() => setDialogOpen(true)}
      >
        Revoke all sessions &amp; tokens
      </Button>
      <ConfirmRevokeAllDialog
        open={dialogOpen}
        onConfirm={handleConfirm}
        onClose={() => setDialogOpen(false)}
        isPending={revokeAll.isPending}
      />
    </Box>
  );
}
