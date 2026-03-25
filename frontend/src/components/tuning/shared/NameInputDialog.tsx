import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from "@mui/material";

interface NameInputDialogProps {
  open: boolean;
  polygonType: "zone" | "mask" | null;
  polygonName: string;
  onPolygonNameChange: (name: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export function NameInputDialog({
  open,
  polygonType,
  polygonName,
  onPolygonNameChange,
  onConfirm,
  onCancel,
}: NameInputDialogProps) {
  return (
    <Dialog open={open} onClose={onCancel} maxWidth="sm" fullWidth>
      <DialogTitle>
        Enter {polygonType === "zone" ? "Zone" : "Mask"} Name
      </DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          margin="dense"
          label="Name"
          type="text"
          fullWidth
          variant="outlined"
          value={polygonName}
          onChange={(e) => onPolygonNameChange(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === "Enter") {
              onConfirm();
            }
          }}
          placeholder={polygonType === "zone" ? "Zone" : "Mask"}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button onClick={onConfirm} variant="contained">
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
