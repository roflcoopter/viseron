import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";

import { CameraPickerGrid } from "components/camera/CameraPickerGrid";

type CameraPickerDialogProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
};
export const CameraPickerDialog = ({
  open,
  setOpen,
}: CameraPickerDialogProps) => {
  const handleClose = () => {
    setOpen(false);
  };

  return (
    <Dialog fullWidth maxWidth={false} open={open} onClose={handleClose}>
      <DialogTitle>Cameras</DialogTitle>
      <DialogContent onClick={handleClose}>
        <CameraPickerGrid />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};
