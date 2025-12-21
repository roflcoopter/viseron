import { AddAlt, TrashCan } from "@carbon/icons-react";
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";

import { ZoneLabel } from "./types";

interface ZoneLabelsDialogProps {
  open: boolean;
  zoneLabels: ZoneLabel[];
  availableLabels: string[];
  onZoneLabelsChange: (labels: ZoneLabel[]) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ZoneLabelsDialog({
  open,
  zoneLabels,
  availableLabels,
  onZoneLabelsChange,
  onConfirm,
  onCancel,
}: ZoneLabelsDialogProps) {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newConfidence, setNewConfidence] = useState(0.8);
  const [newTriggerRecording, setNewTriggerRecording] = useState(true);

  // Get labels that are already in the zone
  const usedLabels = zoneLabels.map((l) => l.label);

  // Filter available labels to only show those not already added
  const availableLabelsForAdd = availableLabels.filter(
    (label) => !usedLabels.includes(label),
  );

  const handleAddLabel = () => {
    if (availableLabelsForAdd.length === 0) return;
    setNewLabel(availableLabelsForAdd[0]);
    setNewConfidence(0.8);
    setNewTriggerRecording(true);
    setShowAddDialog(true);
  };

  const handleConfirmAdd = () => {
    const newLabelItem: ZoneLabel = {
      label: newLabel,
      confidence: newConfidence,
      trigger_event_recording: newTriggerRecording,
    };
    onZoneLabelsChange([...zoneLabels, newLabelItem]);
    setShowAddDialog(false);
  };

  const handleDeleteLabel = (index: number) => {
    onZoneLabelsChange(zoneLabels.filter((_, i) => i !== index));
  };

  const handleEditLabel = (
    index: number,
    field: keyof ZoneLabel,
    value: any,
  ) => {
    const updated = [...zoneLabels];
    updated[index] = { ...updated[index], [field]: value };
    onZoneLabelsChange(updated);
  };

  return (
    <>
      <Dialog open={open} onClose={onCancel} maxWidth="md" fullWidth>
        <DialogTitle>Manage Zone Labels</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                mb: 2,
              }}
            >
              <Typography variant="body2" color="text.secondary">
                Configure labels to detect in this zone
              </Typography>
              <Button
                size="small"
                startIcon={<AddAlt size={16} />}
                onClick={handleAddLabel}
                disabled={availableLabelsForAdd.length === 0}
              >
                Add Label
              </Button>
            </Box>

            {zoneLabels.length === 0 ? (
              <Typography
                variant="caption"
                color="text.secondary"
                display="block"
                sx={{ textAlign: "center", py: 3 }}
              >
                No labels configured. Click &quot;Add Label&quot; to add one.
              </Typography>
            ) : (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {zoneLabels.map((labelItem, index) => (
                  <Box
                    key={`${labelItem.label}-${labelItem.confidence}-${labelItem.trigger_event_recording}`}
                    sx={{
                      display: "flex",
                      gap: 1,
                      alignItems: "flex-start",
                      p: 2,
                      border: 1,
                      borderColor: "divider",
                      borderRadius: 1,
                    }}
                  >
                    <Box sx={{ flexGrow: 1 }}>
                      <TextField
                        select
                        fullWidth
                        label="Label"
                        value={labelItem.label}
                        onChange={(e) =>
                          handleEditLabel(index, "label", e.target.value)
                        }
                        size="small"
                        sx={{ mb: 1 }}
                      >
                        {availableLabels
                          .filter(
                            (l) =>
                              l === labelItem.label || !usedLabels.includes(l),
                          )
                          .map((label) => (
                            <MenuItem
                              key={label}
                              value={label}
                              sx={{ textTransform: "capitalize" }}
                            >
                              {label}
                            </MenuItem>
                          ))}
                      </TextField>

                      <TextField
                        fullWidth
                        label="Confidence"
                        type="number"
                        value={labelItem.confidence}
                        onChange={(e) =>
                          handleEditLabel(
                            index,
                            "confidence",
                            parseFloat(e.target.value),
                          )
                        }
                        size="small"
                        inputProps={{
                          min: 0,
                          max: 1,
                          step: 0.01,
                        }}
                        helperText={`${Math.round(labelItem.confidence * 100)}%`}
                        sx={{ mb: 1 }}
                      />

                      <FormControlLabel
                        control={
                          <Switch
                            checked={labelItem.trigger_event_recording}
                            onChange={(e) =>
                              handleEditLabel(
                                index,
                                "trigger_event_recording",
                                e.target.checked,
                              )
                            }
                            size="small"
                            color="primary"
                          />
                        }
                        label={
                          <Typography variant="body2">
                            Trigger Event Recording
                          </Typography>
                        }
                      />
                    </Box>
                    <IconButton
                      onClick={() => handleDeleteLabel(index)}
                      color="error"
                      size="small"
                      sx={{ mt: 0.5 }}
                    >
                      <TrashCan size={20} />
                    </IconButton>
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onCancel}>Cancel</Button>
          <Button onClick={onConfirm} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add Label Dialog */}
      <Dialog
        open={showAddDialog}
        onClose={() => setShowAddDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add Label to Zone</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              select
              fullWidth
              label="Label"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              margin="normal"
              variant="outlined"
              SelectProps={{
                MenuProps: {
                  PaperProps: {
                    sx: {
                      "& .MuiMenuItem-root": {
                        textTransform: "capitalize",
                      },
                    },
                  },
                },
              }}
            >
              {availableLabelsForAdd.map((label) => (
                <MenuItem key={label} value={label}>
                  {label}
                </MenuItem>
              ))}
            </TextField>

            <TextField
              fullWidth
              label="Confidence"
              type="number"
              value={newConfidence}
              onChange={(e) => setNewConfidence(parseFloat(e.target.value))}
              margin="normal"
              variant="outlined"
              inputProps={{
                min: 0,
                max: 1,
                step: 0.01,
              }}
              helperText={`${Math.round(newConfidence * 100)}%`}
            />

            <FormControlLabel
              control={
                <Switch
                  checked={newTriggerRecording}
                  onChange={(e) => setNewTriggerRecording(e.target.checked)}
                  color="primary"
                />
              }
              label="Trigger Event Recording"
              sx={{ mt: 2 }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowAddDialog(false)}>Cancel</Button>
          <Button onClick={handleConfirmAdd} variant="contained">
            Add
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
