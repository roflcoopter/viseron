import { Help } from "@carbon/icons-react";
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Tooltip,
  Typography,
  tableCellClasses,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";

import { useGetPtzNodes } from "lib/api/actions/onvif/ptz";

import { QueryWrapper } from "../../config/QueryWrapper";

interface PTZMovementsProps {
  cameraIdentifier: string;
}

export function PTZMovements({ cameraIdentifier }: PTZMovementsProps) {
  const theme = useTheme();
  const {
    data: ptzNodes,
    isLoading,
    isError,
    error,
  } = useGetPtzNodes(cameraIdentifier);

  const ptzMovementsItems: { label: string; value: string | undefined }[] = [];

  if (ptzNodes?.nodes && ptzNodes.nodes.length > 0) {
    const firstNode = ptzNodes.nodes[0];

    // Extract PTZ Spaces/Capabilities
    const spaces = firstNode.SupportedPTZSpaces;
    if (spaces) {
      const absolutePanTilt = spaces.AbsolutePanTiltPositionSpace?.[0];
      if (absolutePanTilt) {
        ptzMovementsItems.push({
          label: "Absolute PanTilt",
          value: `Pan [min: ${absolutePanTilt.XRange?.Min}, max: ${absolutePanTilt.XRange?.Max}]\nTilt [min: ${absolutePanTilt.YRange?.Min}, max: ${absolutePanTilt.YRange?.Max}]`,
        });
      } else {
        ptzMovementsItems.push({
          label: "Absolute PanTilt",
          value: "Not Supported",
        });
      }
      const absoluteZoom = spaces.AbsoluteZoomPositionSpace?.[0];
      if (absoluteZoom) {
        ptzMovementsItems.push({
          label: "Absolute Zoom",
          value: `Zoom [min: ${absoluteZoom.XRange?.Min}, max: ${absoluteZoom.XRange?.Max}]`,
        });
      } else {
        ptzMovementsItems.push({
          label: "Absolute Zoom",
          value: "Not Supported",
        });
      }
      const releativePanTilt = spaces.RelativePanTiltTranslationSpace?.[0];
      if (releativePanTilt) {
        ptzMovementsItems.push({
          label: "Relative PanTilt",
          value: `Pan [min: ${releativePanTilt.XRange?.Min}, max: ${releativePanTilt.XRange?.Max}]\nTilt [min: ${releativePanTilt.YRange?.Min}, max: ${releativePanTilt.YRange?.Max}]`,
        });
      } else {
        ptzMovementsItems.push({
          label: "Relative PanTilt",
          value: "Not Supported",
        });
      }
      const relativeZoom = spaces.RelativeZoomTranslationSpace?.[0];
      if (relativeZoom) {
        ptzMovementsItems.push({
          label: "Relative Zoom",
          value: `Zoom [min: ${relativeZoom.XRange?.Min}, max: ${relativeZoom.XRange?.Max}]`,
        });
      } else {
        ptzMovementsItems.push({
          label: "Relative Zoom",
          value: "Not Supported",
        });
      }
      const continuousPanTilt = spaces.ContinuousPanTiltVelocitySpace?.[0];
      if (continuousPanTilt) {
        ptzMovementsItems.push({
          label: "Continuous PanTilt",
          value: `Pan [min: ${continuousPanTilt.XRange?.Min}, max: ${continuousPanTilt.XRange?.Max}]\nTilt [min: ${continuousPanTilt.YRange?.Min}, max: ${continuousPanTilt.YRange?.Max}]`,
        });
      } else {
        ptzMovementsItems.push({
          label: "Continuous PanTilt",
          value: "Not Supported",
        });
      }
      const continuousZoom = spaces.ContinuousZoomVelocitySpace?.[0];
      if (continuousZoom) {
        ptzMovementsItems.push({
          label: "Continuous Zoom",
          value: `Zoom [min: ${continuousZoom.XRange?.Min}, max: ${continuousZoom.XRange?.Max}]`,
        });
      } else {
        ptzMovementsItems.push({
          label: "Continuous Zoom",
          value: "Not Supported",
        });
      }
      const panTiltSpeed = spaces.PanTiltSpeedSpace?.[0];
      if (panTiltSpeed) {
        ptzMovementsItems.push({
          label: "PanTilt Speed",
          value: `Pan [min: ${panTiltSpeed.XRange?.Min ?? "-"}, max: ${panTiltSpeed.XRange?.Max ?? "-"}]\nTilt [min: ${panTiltSpeed.YRange?.Min ?? "-"}, max: ${panTiltSpeed.YRange?.Max ?? "-"}]`,
        });
      } else {
        ptzMovementsItems.push({
          label: "PanTilt Speed",
          value: "Not defined",
        });
      }
      const zoomSpeed = spaces.ZoomSpeedSpace?.[0];
      if (zoomSpeed) {
        ptzMovementsItems.push({
          label: "Zoom Speed",
          value: `Zoom [min: ${zoomSpeed.XRange?.Min ?? "-"}, max: ${zoomSpeed.XRange?.Max ?? "-"}]`,
        });
      } else {
        ptzMovementsItems.push({
          label: "Zoom Speed",
          value: "Not defined",
        });
      }
    }

    // Extract other PTZ capabilities
    const maxPresets = firstNode.MaximumNumberOfPresets;
    if (maxPresets !== undefined) {
      ptzMovementsItems.push({
        label: "Max PTZ Presets",
        value: maxPresets.toString(),
      });
    }

    const homeSupported = firstNode.HomeSupported;
    if (homeSupported !== undefined) {
      ptzMovementsItems.push({
        label: "Home Supported",
        value: homeSupported ? "Yes" : "No",
      });
    }
  }

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={
        error?.message || "Failed to load ptz movements information"
      }
      isEmpty={!ptzNodes || ptzNodes.nodes.length === 0}
      emptyMessage="No ptz capabilities information available"
      showEmptyAlert
      title="PTZ Capabilities"
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="subtitle2">PTZ Capabilities</Typography>
            <Tooltip
              title="READ-ONLY: List of ONVIF PTZ service capabilities of the device."
              arrow
              placement="top"
            >
              <Help size={16} />
            </Tooltip>
          </Box>
        </Box>
        <TableContainer>
          <Table
            size="small"
            sx={{
              [`& .${tableCellClasses.root}`]: {
                borderBottom: `1px solid ${theme.palette.divider}`,
              },
              "& tr:first-of-type td": {
                borderTop: `1px solid ${theme.palette.divider}`,
              },
            }}
          >
            <TableBody>
              {ptzMovementsItems
                .filter((item) => item.value)
                .map((item) => (
                  <TableRow key={item.label}>
                    <TableCell
                      sx={{
                        py: 1,
                        pl: 0,
                        width: "39%",
                        color: "text.secondary",
                      }}
                    >
                      <Typography variant="body2">{item.label}</Typography>
                    </TableCell>
                    <TableCell sx={{ py: 1, pr: 0 }}>
                      <Typography
                        variant="body2"
                        sx={{ whiteSpace: "pre-line" }}
                      >
                        {item.value}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </QueryWrapper>
  );
}
