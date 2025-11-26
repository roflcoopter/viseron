import {
  AddAlt,
  Camera,
  ReflectHorizontal,
  ReflectVertical,
  WatsonHealthRotate_180 as Rotate180,
  Video,
} from "@carbon/icons-react";
import { Box, Button, Typography } from "@mui/material";
import { MouseEvent } from "react";

import { VideoTransform } from "../camera/types";

interface VideoTransformsSectionProps {
  videoTransforms: VideoTransform[];
  selectedVideoTransformIndex: number | null;
  isDrawingMode: boolean;
  isSaving: boolean;
  onAddVideoTransform: (type: "camera" | "recorder") => void;
  onVideoTransformClick: (index: number) => void;
  onContextMenu: (
    event: MouseEvent<HTMLButtonElement>,
    type: "video_transform",
    index: number,
  ) => void;
}

export function VideoTransformsSection({
  videoTransforms,
  selectedVideoTransformIndex,
  isDrawingMode,
  isSaving,
  onAddVideoTransform,
  onVideoTransformClick,
  onContextMenu,
}: VideoTransformsSectionProps) {
  const getTransformIcon = (transformType: string) => {
    switch (transformType) {
      case "hflip":
        return <ReflectHorizontal size={20} />;
      case "vflip":
        return <ReflectVertical size={20} />;
      case "rotate180":
        return <Rotate180 size={20} />;
      default:
        return <Video size={20} />;
    }
  };

  const getTransformLabel = (transformType: string) => {
    switch (transformType) {
      case "hflip":
        return "Horizontal Flip";
      case "vflip":
        return "Vertical Flip";
      case "rotate180":
        return "Rotate 180°";
      default:
        return transformType;
    }
  };

  return (
    <Box mb={3} mt={2}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 1,
        }}
      >
        <Typography variant="subtitle2">Video Transforms</Typography>
        <Box display="flex" gap={0.5}>
          <Button
            size="small"
            startIcon={<AddAlt size={16} />}
            onClick={() => onAddVideoTransform("camera")}
            disabled={isDrawingMode || isSaving}
            title="Add OSD Text"
          >
            Add
          </Button>
        </Box>
      </Box>

      {videoTransforms.length === 0 ? (
        <Typography
          variant="caption"
          color="text.secondary"
          display="block"
          sx={{ ml: 1 }}
        >
          No video transforms configured
        </Typography>
      ) : (
        videoTransforms.map((transform, index) => (
          <Button
            key={transform.id}
            variant={
              selectedVideoTransformIndex === index ? "contained" : "outlined"
            }
            fullWidth
            onClick={() => onVideoTransformClick(index)}
            onContextMenu={(e) => onContextMenu(e, "video_transform", index)}
            disabled={isDrawingMode || isSaving}
            color={transform.type === "camera" ? "info" : "secondary"}
            sx={{
              mb: 1,
              p: 1.5,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              textTransform: "none",
            }}
            startIcon={getTransformIcon(transform.transform)}
          >
            <Typography
              variant="body2"
              sx={{
                flexGrow: 1,
                textAlign: "left",
                fontWeight: 500,
              }}
            >
              {getTransformLabel(transform.transform)}
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              {transform.type === "camera" ? (
                <Camera size={16} color="text.secondary" />
              ) : (
                <Video size={16} color="text.secondary" />
              )}
              <Typography variant="caption">{transform.type}</Typography>
            </Box>
          </Button>
        ))
      )}
    </Box>
  );
}
