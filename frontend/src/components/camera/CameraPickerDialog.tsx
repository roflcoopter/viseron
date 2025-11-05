import { Video } from "@carbon/icons-react";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import { CameraPickerGrid } from "components/camera/CameraPickerGrid";

type CameraPickerDialogProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
};
export function CameraPickerDialog({ open, setOpen }: CameraPickerDialogProps) {
  const handleClose = () => {
    setOpen(false);
  };

  return (
    <Dialog 
      fullWidth 
      maxWidth={false} 
      open={open} 
      onClose={handleClose}
      disablePortal={false}
      container={() => document.body}
      style={{ zIndex: 9001 }}
      BackdropProps={{
        style: { zIndex: 9001 }
      }}
      PaperProps={{
        style: { zIndex: 9002, position: 'relative' }
      }}
    >
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Video size={24} />
          <Typography variant="h6">Select Cameras</Typography>
        </Stack>
      </DialogTitle>
      <DialogContent onClick={handleClose}>
        <CameraPickerGrid />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
