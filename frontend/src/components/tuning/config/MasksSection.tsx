import { AddAlt, Area } from "@carbon/icons-react";
import { Box, Button, Typography } from "@mui/material";
import { MouseEvent } from "react";

import { Mask } from "../shared/types";

interface MasksSectionProps {
  masks: Mask[];
  selectedMaskIndex: number | null;
  isDrawingMode: boolean;
  isSaving: boolean;
  onMaskClick: (index: number) => void;
  onAddMask: () => void;
  onContextMenu: (
    event: MouseEvent<HTMLButtonElement>,
    type: "mask",
    index: number,
  ) => void;
}

export function MasksSection({
  masks,
  selectedMaskIndex,
  isDrawingMode,
  isSaving,
  onMaskClick,
  onAddMask,
  onContextMenu,
}: MasksSectionProps) {
  return (
    <Box mb={2.5}>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={1}
      >
        <Typography variant="subtitle2">Masks</Typography>
        <Button
          size="small"
          startIcon={<AddAlt size={16} />}
          onClick={onAddMask}
          disabled={isDrawingMode || isSaving}
        >
          Add
        </Button>
      </Box>
      {masks && Array.isArray(masks) && masks.length > 0 ? (
        <Box display="flex" flexDirection="column" gap={1}>
          {masks.map((mask: Mask, index: number) => (
            <Button
              key={
                mask.name ||
                `mask-${JSON.stringify(mask.coordinates?.[0])}-${index}`
              }
              variant={selectedMaskIndex === index ? "contained" : "outlined"}
              fullWidth
              sx={{ justifyContent: "flex-start" }}
              onClick={() => onMaskClick(index)}
              onContextMenu={(e) => onContextMenu(e, "mask", index)}
              disabled={isDrawingMode || isSaving}
              color="error"
              startIcon={<Area />}
            >
              {mask.name || `Mask ${index + 1}`}
            </Button>
          ))}
        </Box>
      ) : (
        <Typography
          variant="caption"
          color="text.secondary"
          display="block"
          sx={{ ml: 1 }}
        >
          No masks configured
        </Typography>
      )}
    </Box>
  );
}
