import { AddAlt, GlobalFilters, Help, TrashCan } from "@carbon/icons-react";
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormHelperText,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  TextField,
  Tooltip,
  Typography,
  tableCellClasses,
} from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useEffect, useState } from "react";

import { useToast } from "hooks/UseToast";
import { useFormChanges } from "hooks/useFormChanges";
import { useGetDeviceNTP, useSetDeviceNTP } from "lib/api/actions/onvif/device";

import { QueryWrapper } from "../../config/QueryWrapper";

type NTPType = "IPv4" | "IPv6" | "DNS" | "";

interface NTPServerEntry {
  id: string;
  type: NTPType;
  server: string;
}

let ntpServerIdCounter = 0;
const generateNtpServerId = () => `ntp-server-${++ntpServerIdCounter}`;

interface DeviceNTPProps {
  cameraIdentifier: string;
  deviceCapabilities?: any;
}

export function DeviceNTP({
  cameraIdentifier,
  deviceCapabilities,
}: DeviceNTPProps) {
  // Check if network configuration is not supported
  const isNetworkConfigNotSupported =
    deviceCapabilities?.System?.NetworkConfigNotSupported === true;

  // Check max NTP servers supported (NTP > 1 means multiple NTP servers can be configured)
  const maxNTPServers = deviceCapabilities?.Network?.NTP ?? 1;
  const supportsMultipleNTP = maxNTPServers > 1;

  const TITLE = "NTP Settings";
  const DESC =
    "Manage Network Time Protocol (NTP) settings for network-based time synchronization. Changes to the 'NTP Servers' list will be ignored if 'NTP From DHCP' is enabled.";

  const theme = useTheme();
  const toast = useToast();

  // ONVIF API hooks
  const { data, isLoading, isError, error } = useGetDeviceNTP(
    cameraIdentifier,
    !isNetworkConfigNotSupported,
  );
  const setNTPMutation = useSetDeviceNTP(cameraIdentifier);

  const ntp = data?.ntp;
  const infoItems: { label: string; value: string }[] = [];

  // Section state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [NTPFromDHCP, setNTPFromDHCP] = useState<boolean>(false);
  const [ntpServers, setNtpServers] = useState<NTPServerEntry[]>([
    { id: generateNtpServerId(), type: "", server: "" },
  ]);
  const [originalValues, setOriginalValues] = useState<{
    NTPFromDHCP: boolean;
    ntpServers: NTPServerEntry[];
  }>({
    NTPFromDHCP: false,
    ntpServers: [{ id: generateNtpServerId(), type: "", server: "" }],
  });

  // Data extraction for display
  if (ntp) {
    if (ntp.FromDHCP !== undefined) {
      infoItems.push({
        label: "From DHCP",
        value: ntp.FromDHCP ? "Enabled" : "Disabled",
      });
    }
    const addNtpServers = (servers?: Array<Record<string, any>>) => {
      if (!servers?.length) {
        return false;
      }

      const serverFields = ["IPv4Address", "IPv6Address", "DNSname"] as const;

      servers.forEach((server, index) => {
        serverFields.forEach((field) => {
          if (server?.[field]) {
            infoItems.push({
              label: `NTP Type (#${index + 1})`,
              value: server.Type || "N/A",
            });
            infoItems.push({
              label: `NTP Server (#${index + 1})`,
              value: server[field],
            });
          }
        });
      });

      return true;
    };

    const hasServers = ntp.FromDHCP
      ? addNtpServers(ntp.NTPFromDHCP)
      : addNtpServers(ntp.NTPManual);

    if (!hasServers) {
      infoItems.push({
        label: "NTP Servers",
        value: "Not Configured",
      });
    }
  }

  useEffect(() => {
    if (ntp?.FromDHCP !== undefined) {
      setNTPFromDHCP(ntp.FromDHCP);
    }
  }, [ntp?.FromDHCP]);

  // Handlers
  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  const handleOpenDialog = () => {
    const fromDhcp = ntp?.FromDHCP ?? false;

    const parseNtpServers = (
      servers?: Array<Record<string, any>>,
    ): NTPServerEntry[] => {
      if (!servers?.length) {
        return [{ id: generateNtpServerId(), type: "", server: "" }];
      }

      return servers.map((server) => {
        const id = generateNtpServerId();
        if (server?.Type === "DNS" && server?.DNSname) {
          return { id, type: "DNS" as const, server: server.DNSname };
        }
        if (server?.Type === "IPv4" && server?.IPv4Address) {
          return { id, type: "IPv4" as const, server: server.IPv4Address };
        }
        if (server?.Type === "IPv6" && server?.IPv6Address) {
          return { id, type: "IPv6" as const, server: server.IPv6Address };
        }
        // Fallback
        if (server?.IPv4Address) {
          return { id, type: "IPv4" as const, server: server.IPv4Address };
        }
        if (server?.IPv6Address) {
          return { id, type: "IPv6" as const, server: server.IPv6Address };
        }
        if (server?.DNSname) {
          return { id, type: "DNS" as const, server: server.DNSname };
        }
        return { id, type: "" as const, server: "" };
      });
    };

    const serverSource = fromDhcp ? ntp?.NTPFromDHCP : ntp?.NTPManual;
    const parsedServers = parseNtpServers(serverSource);

    setNTPFromDHCP(fromDhcp);
    setNtpServers(parsedServers);
    setOriginalValues({
      NTPFromDHCP: fromDhcp,
      ntpServers: parsedServers.map((s) => ({ ...s })),
    });
    setDialogOpen(true);
  };

  const handleAddServer = () => {
    if (ntpServers.length < maxNTPServers) {
      setNtpServers([
        ...ntpServers,
        { id: generateNtpServerId(), type: "", server: "" },
      ]);
    }
  };

  const handleRemoveServer = (index: number) => {
    if (ntpServers.length > 1) {
      setNtpServers(ntpServers.filter((_, i) => i !== index));
    }
  };

  const handleServerChange = (
    index: number,
    field: "type" | "server",
    value: string,
  ) => {
    const updated = ntpServers.map((server, i) =>
      i === index ? { ...server, [field]: value } : server,
    );
    setNtpServers(updated);
  };

  // Check if there are any changes
  const hasChanges = useFormChanges(
    { NTPFromDHCP, ntpServers },
    originalValues,
    {
      ntpServers: (current: NTPServerEntry[], original: NTPServerEntry[]) => {
        if (current.length !== original.length) return false;
        return current.every(
          (server, i) =>
            server.type === original[i]?.type &&
            server.server === original[i]?.server,
        );
      },
    },
  );

  // Validate servers when not using DHCP
  const isServersValid =
    NTPFromDHCP ||
    ntpServers.every((server) => server.type && server.server.trim());

  const handleUpdateNTP = () => {
    // Build the NTP manual configuration array from valid servers
    const validServers = ntpServers.filter((s) => s.type && s.server.trim());
    const ntpManualConfig =
      validServers.length > 0
        ? validServers.map((s) => {
            const serverConfig: Record<string, string> = { Type: s.type };
            if (s.type === "IPv4") {
              serverConfig.IPv4Address = s.server.trim();
            } else if (s.type === "IPv6") {
              serverConfig.IPv6Address = s.server.trim();
            } else if (s.type === "DNS") {
              serverConfig.DNSname = s.server.trim();
            }
            return serverConfig;
          })
        : undefined;

    setNTPMutation.mutate(
      {
        from_dhcp: NTPFromDHCP,
        ntp_manual: ntpManualConfig,
      },
      {
        onSuccess: () => {
          toast.success("NTP settings updated successfully");
          setDialogOpen(false);
        },
        onError: () => {
          toast.error("Failed to update NTP settings");
        },
      },
    );
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load device NTP settings"}
      isEmpty={infoItems.length === 0}
      isWarning={isNetworkConfigNotSupported}
      warningMessage="Network configuration is not supported by this device"
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
          <Button
            size="small"
            startIcon={<GlobalFilters size={16} />}
            onClick={handleOpenDialog}
            disabled={isNetworkConfigNotSupported}
          >
            Configure
          </Button>
        </Box>

        {/* NTP Table */}
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
                    <Typography variant="body2">{item.label}</Typography>
                  </TableCell>
                  <TableCell sx={{ py: 1, pr: 0 }}>
                    <Typography variant="body2">{item.value}</Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        {/* NTP Configuration Dialog */}
        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>
            <Box
              display="flex"
              justifyContent="space-between"
              alignItems="center"
              gap={1}
            >
              <Typography variant="inherit">
                Configure Network Time Protocol
              </Typography>
              <Typography variant="caption" fontWeight="medium" color="primary">
                {`Max NTP Servers: ${maxNTPServers}`}
              </Typography>
            </Box>
          </DialogTitle>
          <DialogContent>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
            >
              <FormControl fullWidth>
                <InputLabel>NTP From DHCP</InputLabel>
                <Select
                  value={NTPFromDHCP ? "Enabled" : "Disabled"}
                  label="NTP From DHCP"
                  onChange={(e) => setNTPFromDHCP(e.target.value === "Enabled")}
                >
                  <MenuItem value="Enabled">Enabled</MenuItem>
                  <MenuItem value="Disabled">Disabled</MenuItem>
                </Select>
                <FormHelperText>
                  Set whether the device obtains NTP settings from DHCP.
                </FormHelperText>
              </FormControl>
              <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {ntpServers.map((serverEntry, index) => (
                  <Box
                    key={serverEntry.id}
                    sx={{
                      display: "flex",
                      gap: 2,
                      alignItems: "center",
                    }}
                  >
                    <FormControl sx={{ minWidth: 120 }}>
                      <InputLabel>Type</InputLabel>
                      <Select
                        value={serverEntry.type}
                        label="Type"
                        disabled={NTPFromDHCP}
                        onChange={(e) =>
                          handleServerChange(index, "type", e.target.value)
                        }
                      >
                        <MenuItem value="IPv4">IPv4</MenuItem>
                        <MenuItem value="IPv6">IPv6</MenuItem>
                        <MenuItem value="DNS">DNS</MenuItem>
                      </Select>
                    </FormControl>
                    <TextField
                      fullWidth
                      disabled={NTPFromDHCP}
                      label={`NTP Server #${index + 1}`}
                      value={serverEntry.server}
                      onChange={(e) =>
                        handleServerChange(index, "server", e.target.value)
                      }
                      placeholder="e.g., pool.ntp.org or 192.168.1.1"
                      error={
                        !NTPFromDHCP &&
                        (!serverEntry.type || !serverEntry.server.trim())
                      }
                    />
                    {ntpServers.length > 1 && (
                      <IconButton
                        size="small"
                        onClick={() => handleRemoveServer(index)}
                        color="error"
                        disabled={NTPFromDHCP}
                      >
                        <TrashCan size={20} />
                      </IconButton>
                    )}
                  </Box>
                ))}
                {supportsMultipleNTP && (
                  <Button
                    startIcon={<AddAlt size={16} />}
                    onClick={handleAddServer}
                    variant="outlined"
                    disabled={NTPFromDHCP || ntpServers.length >= maxNTPServers}
                  >
                    Add Server
                  </Button>
                )}
              </Box>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Cancel</Button>
            <Button
              onClick={handleUpdateNTP}
              variant="contained"
              disabled={
                setNTPMutation.isPending || !hasChanges || !isServersValid
              }
            >
              {setNTPMutation.isPending ? (
                <CircularProgress enableTrackSlot size={24} />
              ) : (
                "Save"
              )}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </QueryWrapper>
  );
}
