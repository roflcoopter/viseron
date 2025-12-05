import {
  AddAlt,
  Label as LabelIcon,
  TextCreation,
  User,
} from "@carbon/icons-react";
import { Box, Button, Typography } from "@mui/material";
import { MouseEvent } from "react";

import { Label } from "../object_detector/types";

interface LabelsSectionProps {
  labels: Label[] | string[]; // Support both object_detector (Label[]) and face_recognition (string[])
  isDrawingMode: boolean;
  isSaving: boolean;
  componentType?: string; // To determine which icon to use
  onLabelClick: (index: number) => void;
  onAddLabel: () => void;
  onContextMenu: (
    event: MouseEvent<HTMLButtonElement>,
    type: "label",
    index: number,
  ) => void;
}

export function LabelsSection({
  labels,
  isDrawingMode,
  isSaving,
  componentType,
  onLabelClick,
  onAddLabel,
  onContextMenu,
}: LabelsSectionProps) {
  return (
    <Box mb={2}>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={1}
      >
        <Typography variant="subtitle2">Labels</Typography>
        <Button
          size="small"
          startIcon={<AddAlt size={16} />}
          onClick={onAddLabel}
          disabled={isDrawingMode || isSaving}
        >
          Add
        </Button>
      </Box>
      {labels && Array.isArray(labels) && labels.length > 0 ? (
        labels.map((labelItem: Label | string, index: number) => {
          // Check if labelItem is a string (face_recognition) or Label object (object_detector)
          const isStringLabel = typeof labelItem === "string";
          const labelText = isStringLabel ? labelItem : labelItem.label;
          const confidence = isStringLabel ? undefined : labelItem.confidence;

          // Select icon based on componentType
          const IconComponent =
            componentType === "face_recognition"
              ? User
              : componentType === "license_plate_recognition"
                ? LabelIcon
                : TextCreation;

          return (
            <Button
              key={labelText || `label-${index}`}
              variant="outlined"
              fullWidth
              onClick={() => onLabelClick(index)}
              onContextMenu={(e) => onContextMenu(e, "label", index)}
              color="info"
              disabled={isDrawingMode || isSaving}
              sx={{
                mb: 1,
                p: 1.5,
                display: "flex",
                justifyContent: "flex-start",
                textTransform: "none",
              }}
            >
              <IconComponent style={{ marginRight: 8, flexShrink: 0 }} />
              <Typography
                variant="body2"
                sx={{
                  textTransform: "uppercase",
                  fontWeight: 500,
                  flexGrow: 1,
                  textAlign: "left",
                }}
              >
                {labelText || `Label ${index + 1}`}
              </Typography>
              {confidence !== undefined && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ flexShrink: 0 }}
                >
                  {Math.round((confidence ?? 0.8) * 100)}%
                </Typography>
              )}
            </Button>
          );
        })
      ) : (
        <Typography
          variant="caption"
          color="text.secondary"
          display="block"
          sx={{ ml: 1 }}
        >
          No labels configured
        </Typography>
      )}
    </Box>
  );
}
