import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Switch,
  TextField,
} from "@mui/material";

interface LabelDialogProps {
  open: boolean;
  isEdit: boolean;
  label: string;
  confidence?: number;
  triggerRecording?: boolean;
  availableLabels?: string[];
  existingLabels?: string[]; // All existing labels to check for duplicates
  originalLabel?: string; // The original label when editing (to exclude from duplicate check)
  onLabelChange: (label: string) => void;
  onConfidenceChange?: (confidence: number) => void;
  onTriggerRecordingChange?: (checked: boolean) => void;
  onConfirm: () => void;
  onCancel: () => void;
  showConfidence?: boolean;
  showTriggerRecording?: boolean;
  useTextInput?: boolean;
  inputType?: "face" | "plate" | "object"; // To customize helper text and placeholder
}

export function LabelDialog({
  open,
  isEdit,
  label,
  confidence = 0.8,
  triggerRecording = true,
  availableLabels,
  existingLabels = [],
  originalLabel,
  onLabelChange,
  onConfidenceChange,
  onTriggerRecordingChange,
  onConfirm,
  onCancel,
  showConfidence = true,
  showTriggerRecording = true,
  useTextInput = false,
  inputType = "face",
}: LabelDialogProps) {
  // Use availableLabels from parent - they are already filtered to exclude existing labels
  const labels = availableLabels || [];

  // Auto-detect if we should use text input: if no available labels, use text input
  const shouldUseTextInput = useTextInput || labels.length === 0;

  // Check if the current label already exists (case-insensitive for text input)
  // When editing, exclude the original label from duplicate check
  const isDuplicate =
    shouldUseTextInput &&
    existingLabels.some(
      (existingLabel) =>
        existingLabel.toLowerCase() === label.toLowerCase().trim() &&
        existingLabel.toLowerCase() !== originalLabel?.toLowerCase(),
    );

  // Disable confirm button if label is empty or duplicate
  const isConfirmDisabled =
    !label.trim() || (shouldUseTextInput && isDuplicate);

  // Get helper text and placeholder based on input type
  const getHelperText = () => {
    if (inputType === "face") {
      return "Enter the label of the person to recognize";
    }
    if (inputType === "plate") {
      return "Enter the license plate number";
    }
    return "Enter the label name";
  };

  const getPlaceholder = () => {
    if (inputType === "face") {
      return "e.g., John Doe";
    }
    if (inputType === "plate") {
      return "e.g., ABC-1234";
    }
    return "e.g., person";
  };

  return (
    <Dialog open={open} onClose={onCancel} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? "Edit" : "Add"} Label</DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 1 }}>
          {shouldUseTextInput ? (
            <TextField
              fullWidth
              label="Label"
              value={label}
              onChange={(e) => onLabelChange(e.target.value)}
              margin="normal"
              variant="outlined"
              autoFocus
              placeholder={getPlaceholder()}
              helperText={
                isDuplicate ? "This label already exists" : getHelperText()
              }
              error={isDuplicate}
            />
          ) : (
            <TextField
              select
              fullWidth
              label="Label"
              value={label}
              onChange={(e) => onLabelChange(e.target.value)}
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
              {labels.map((labelOption) => (
                <MenuItem key={labelOption} value={labelOption}>
                  {labelOption}
                </MenuItem>
              ))}
            </TextField>
          )}

          {showConfidence && (
            <TextField
              fullWidth
              label="Confidence"
              type="number"
              value={confidence}
              onChange={(e) => onConfidenceChange?.(parseFloat(e.target.value))}
              margin="normal"
              variant="outlined"
              inputProps={{
                min: 0,
                max: 1,
                step: 0.01,
              }}
              helperText={`${Math.round(confidence * 100)}%`}
            />
          )}

          {showTriggerRecording && (
            <FormControlLabel
              control={
                <Switch
                  checked={triggerRecording}
                  onChange={(e) => onTriggerRecordingChange?.(e.target.checked)}
                  color="primary"
                />
              }
              label="Trigger Event Recording"
              sx={{ mt: 2 }}
            />
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Cancel</Button>
        <Button
          onClick={onConfirm}
          variant="contained"
          disabled={isConfirmDisabled}
        >
          {isEdit ? "Save" : "Add"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
