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

import { useGetDeviceInformation } from "lib/api/actions/onvif/device";

import { QueryWrapper } from "../../config/QueryWrapper";

interface DeviceInformationProps {
  cameraIdentifier: string;
}

export function DeviceInformation({
  cameraIdentifier,
}: DeviceInformationProps) {
  const TITLE = "Device Information";
  const DESC = "READ-ONLY: List of ONVIF device information.";

  const theme = useTheme();

  // ONVIF API hook
  const { data, isLoading, isError, error } =
    useGetDeviceInformation(cameraIdentifier);

  const info = data?.information;
  const infoItems = info
    ? [
        { label: "Manufacturer", value: info.Manufacturer },
        { label: "Model", value: info.Model },
        { label: "Firmware", value: info.FirmwareVersion },
        { label: "Serial Number", value: info.SerialNumber },
        { label: "Hardware ID", value: info.HardwareId },
      ].filter((item) => item.value)
    : [];

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load device information"}
      isEmpty={!info || infoItems.length === 0}
      title={TITLE}
    >
      <Box>
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems="center"
          mb={1}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="subtitle2">{TITLE}</Typography>
            <Tooltip title={DESC} arrow placement="top">
              <Help size={16} />
            </Tooltip>
          </Box>
        </Box>

        {/* Information Table */}
        <Box>
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
                {infoItems.map((item) => (
                  <TableRow key={item.label}>
                    <TableCell
                      sx={{
                        py: 1,
                        pl: 0,
                        width: "36%",
                        color: "text.secondary",
                      }}
                    >
                      <Typography variant="body2" sx={{ whiteSpace: "nowrap" }}>
                        {item.label}
                      </Typography>
                    </TableCell>
                    <TableCell sx={{ py: 1, pr: 0 }}>
                      <Typography variant="body2">{item.value}</Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </Box>
    </QueryWrapper>
  );
}
