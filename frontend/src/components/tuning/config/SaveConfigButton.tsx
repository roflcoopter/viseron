import { Save } from "@carbon/icons-react";
import { Box, Button } from "@mui/material";

interface SaveConfigButtonProps {
  isConfigModified: boolean;
  isSaving: boolean;
  isDrawingMode: boolean;
  onSaveConfig: () => void;
}

export function SaveConfigButton({
  isConfigModified,
  isSaving,
  isDrawingMode,
  onSaveConfig,
}: SaveConfigButtonProps) {
  return (
    <Box
      mt={2}
      pt={2}
      sx={{
        borderTop: 1,
        borderColor: "divider",
      }}
    >
      <Button
        variant="contained"
        color="primary"
        fullWidth
        startIcon={<Save size={16} />}
        onClick={onSaveConfig}
        disabled={!isConfigModified || isSaving || isDrawingMode}
      >
        {isSaving ? "Saving..." : "Save Config"}
      </Button>
    </Box>
  );
}
