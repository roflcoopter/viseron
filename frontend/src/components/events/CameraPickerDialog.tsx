import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";

import { EventsCameraGrid } from "components/events/EventsCameraGrid";
import * as types from "lib/types";

type CameraPickerDialogProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
  cameras: types.Cameras;
  changeSelectedCamera: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera,
  ) => void;
  selectedCamera: types.Camera | null;
};
export const CameraPickerDialog = ({
  open,
  setOpen,
  cameras,
  changeSelectedCamera,
  selectedCamera,
}: CameraPickerDialogProps) => {
  const handleClose = () => {
    setOpen(false);
  };

  return (
    <Dialog fullWidth maxWidth={false} open={open} onClose={handleClose}>
      <DialogTitle>Cameras</DialogTitle>
      <DialogContent onClick={handleClose}>
        <EventsCameraGrid
          cameras={cameras}
          changeSelectedCamera={changeSelectedCamera}
          selectedCamera={selectedCamera}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};
