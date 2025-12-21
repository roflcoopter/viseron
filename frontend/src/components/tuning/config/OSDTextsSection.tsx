import { AddAlt, Camera, Video } from "@carbon/icons-react";
import { Box, Button, Typography } from "@mui/material";
import { MouseEvent } from "react";

import { OSDText } from "../camera/types";

interface OSDTextsSectionProps {
  osdTexts: OSDText[];
  isDrawingMode: boolean;
  isSaving: boolean;
  selectedOSDTextIndex: number | null;
  onAddOSDText: (type: "camera" | "recorder") => void;
  onOSDTextClick: (index: number) => void;
  onContextMenu: (
    event: MouseEvent<HTMLButtonElement>,
    type: "osd",
    index: number,
  ) => void;
}

export function OSDTextsSection({
  osdTexts,
  isDrawingMode,
  isSaving,
  selectedOSDTextIndex,
  onAddOSDText,
  onOSDTextClick,
  onContextMenu,
}: OSDTextsSectionProps) {
  return (
    <Box mb={2}>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={1}
      >
        <Typography variant="subtitle2">OSD Texts</Typography>
        <Box display="flex" gap={0.5}>
          <Button
            size="small"
            startIcon={<AddAlt size={16} />}
            onClick={() => onAddOSDText("camera")}
            disabled={isDrawingMode || isSaving}
            title="Add OSD Text"
          >
            Add
          </Button>
        </Box>
      </Box>
      {osdTexts && Array.isArray(osdTexts) && osdTexts.length > 0 ? (
        osdTexts.map((osdText: OSDText, index: number) => (
          <Button
            key={osdText.id || `osd-${index}`}
            variant={selectedOSDTextIndex === index ? "contained" : "outlined"}
            fullWidth
            onClick={() => onOSDTextClick(index)}
            onContextMenu={(e) => onContextMenu(e, "osd", index)}
            disabled={isDrawingMode || isSaving}
            color={osdText.type === "camera" ? "info" : "secondary"}
            sx={{
              mb: 1,
              p: 1.5,
              display: "flex",
              justifyContent: "flex-start",
              textTransform: "none",
            }}
            startIcon={
              osdText.type === "camera" ? (
                <Camera size={20} />
              ) : (
                <Video size={20} />
              )
            }
          >
            <Typography
              variant="body2"
              sx={{
                flexGrow: 1,
                textAlign: "left",
                fontWeight: 500,
              }}
            >
              {osdText.textType === "timestamp"
                ? "Timestamp"
                : osdText.customText || "Custom Text"}
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ flexShrink: 0 }}
            >
              {osdText.position} • {osdText.fontSize}px
            </Typography>
          </Button>
        ))
      ) : (
        <Typography
          variant="caption"
          color="text.secondary"
          display="block"
          sx={{ ml: 1 }}
        >
          No OSD texts configured
        </Typography>
      )}
    </Box>
  );
}
