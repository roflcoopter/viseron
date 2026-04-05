import { AddAlt, AreaCustom, Help } from "@carbon/icons-react";
import { Box, Button, Tooltip, Typography } from "@mui/material";
import { MouseEvent } from "react";

import { Zone } from "../object_detector/types";

interface ZonesSectionProps {
  zones: Zone[];
  selectedZoneIndex: number | null;
  isDrawingMode: boolean;
  isSaving: boolean;
  onZoneClick: (index: number) => void;
  onAddZone: () => void;
  onContextMenu: (
    event: MouseEvent<HTMLButtonElement>,
    type: "zone",
    index: number,
  ) => void;
}

export function ZonesSection({
  zones,
  selectedZoneIndex,
  isDrawingMode,
  isSaving,
  onZoneClick,
  onAddZone,
  onContextMenu,
}: ZonesSectionProps) {
  return (
    <Box mb={2}>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={1}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="subtitle2">Zones</Typography>
          <Tooltip
            title="Zones are used to define areas in the cameras field of view where you want to look for certain objects (labels)."
            arrow
            placement="top"
          >
            <Help size={16} />
          </Tooltip>
        </Box>
        <Button
          size="small"
          startIcon={<AddAlt size={16} />}
          onClick={onAddZone}
          disabled={isDrawingMode || isSaving}
        >
          Add
        </Button>
      </Box>
      {zones && Array.isArray(zones) && zones.length > 0 ? (
        <Box display="flex" flexDirection="column" gap={1}>
          {zones.map((zone: Zone, index: number) => (
            <Button
              key={zone.name || `zone-${index}`}
              variant={selectedZoneIndex === index ? "contained" : "outlined"}
              fullWidth
              sx={{ justifyContent: "flex-start" }}
              onClick={() => onZoneClick(index)}
              onContextMenu={(e) => onContextMenu(e, "zone", index)}
              disabled={isDrawingMode || isSaving}
              color="success"
              startIcon={<AreaCustom />}
            >
              {zone.name || `Zone ${index + 1}`}
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
          No zones configured
        </Typography>
      )}
    </Box>
  );
}
