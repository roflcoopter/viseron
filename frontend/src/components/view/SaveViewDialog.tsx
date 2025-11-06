import { Template } from "@carbon/icons-react";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import { useCameraStore } from "components/camera/useCameraStore";
import { useGridLayoutStore } from "stores/GridLayoutStore";
import { useViewStore } from "stores/ViewStore";

interface SaveViewDialogProps {
  open: boolean;
  onClose: () => void;
}

export function SaveViewDialog({ open, onClose }: SaveViewDialogProps) {
  const [viewName, setViewName] = useState("");
  const [error, setError] = useState("");
  
  const { currentLayout, layoutConfig } = useGridLayoutStore();
  const { selectedCameras, selectionOrder } = useCameraStore();
  const { addView, views } = useViewStore();

  const handleClose = () => {
    setViewName("");
    setError("");
    onClose();
  };

  const handleSave = () => {
    if (!viewName.trim()) {
      setError("View name is required");
      return;
    }

    if (selectedCameras.length === 0) {
      setError("Please select at least one camera");
      return;
    }

    if (views.length >= 5) {
      setError("Maximum 5 views allowed");
      return;
    }

    addView({
      name: viewName.trim(),
      layoutType: currentLayout,
      layoutConfig,
      selectedCameras,
      selectionOrder,
    });

    handleClose();
  };

  return (
    <Dialog 
      open={open} 
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
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
          <Template size={24} />
          <Typography variant="h6">Save</Typography>
        </Stack>
      </DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            autoFocus
            label="View Name"
            value={viewName}
            onChange={(e) => {
              setViewName(e.target.value);
              setError("");
            }}
            error={!!error}
            helperText={error}
            fullWidth
            variant="outlined"
            placeholder="Enter view name (e.g., Living Room View)"
          />
          
          <Typography variant="body2" color="text.secondary">
            Current Configuration:
          </Typography>
          <Stack spacing={1} sx={{ pl: 2 }}>
            <Typography variant="body2">
              <strong>Layout:</strong> {currentLayout === 'auto' ? 'Auto Layout' : `Custom ${currentLayout}`}
            </Typography>
            <Typography variant="body2">
              <strong>Cameras:</strong> {selectedCameras.length} selected
            </Typography>
            {selectedCameras.length > 0 && (
              <Typography variant="body2" color="text.secondary">
                {selectionOrder.map((id, index) => `(${index + 1}) ${id}`).join(', ')}
              </Typography>
            )}
          </Stack>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button 
          onClick={handleSave} 
          variant="contained"
          disabled={!viewName.trim() || selectedCameras.length === 0}
        >
          Save View
        </Button>
      </DialogActions>
    </Dialog>
  );
}