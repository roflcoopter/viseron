import { GlobalFilters, Help } from "@carbon/icons-react";
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
import {
  useGetDeviceDiscoveryMode,
  useGetDeviceHostname,
  useGetDeviceNetworkDefaultGateway,
  useSetDeviceDiscoveryMode,
  useSetDeviceHostname,
  useSetDeviceHostnameFromDHCP,
  useSetDeviceNetworkDefaultGateway,
} from "lib/api/actions/onvif/device";

import { QueryWrapper } from "../../config/QueryWrapper";

interface DeviceSettingsProps {
  cameraIdentifier: string;
  deviceCapabilities?: any;
}

export function DeviceNetworkSettings({
  cameraIdentifier,
  deviceCapabilities,
}: DeviceSettingsProps) {
  // Check if network configuration is not supported
  const isNetworkConfigNotSupported =
    deviceCapabilities?.System?.NetworkConfigNotSupported === true;

  // Check if discovery is not supported
  const isDiscoveryNotSupported =
    deviceCapabilities?.System?.DiscoveryNotSupported === true;

  // Check if hostname from DHCP is supported
  const isHostnameFromDHCPSupported =
    deviceCapabilities?.Network?.HostnameFromDHCP === true;

  const TITLE = "Network Settings";
  const DESC =
    "Manage network settings for this device. Usually this configuration will change to 'default value' if the camera do reboot.";

  const theme = useTheme();
  const toast = useToast();

  // ONVIF API hooks
  const { data, isLoading, isError, error } = useGetDeviceNetworkDefaultGateway(
    cameraIdentifier,
    !isNetworkConfigNotSupported,
  );
  const setNetworkGatewayMutation =
    useSetDeviceNetworkDefaultGateway(cameraIdentifier);

  const { data: hostnameData } = useGetDeviceHostname(
    cameraIdentifier,
    !isNetworkConfigNotSupported,
  );
  const setHostnameMutation = useSetDeviceHostname(cameraIdentifier);
  const setHostnameFromDHCPMutation =
    useSetDeviceHostnameFromDHCP(cameraIdentifier);

  const { data: discoveryData } = useGetDeviceDiscoveryMode(
    cameraIdentifier,
    !isDiscoveryNotSupported,
  );
  const setDiscoveryModeMutation = useSetDeviceDiscoveryMode(cameraIdentifier);

  const networkSettingsItems: { label: string; value: string | undefined }[] =
    [];

  const networkGatewayData = data?.network_default_gateway as
    | {
        IPv4Address?: string[];
        IPv6Address?: string[];
      }
    | undefined;

  // Section state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [ipVersion, setIpVersion] = useState<"ipv4" | "ipv6">("ipv4");
  const [ipv4Address, setIpv4Address] = useState("");
  const [ipv6Address, setIpv6Address] = useState("");
  const [hostnameFromDHCP, setHostnameFromDHCP] = useState(false);
  const [hostname, setHostname] = useState("");
  const [discoveryMode, setDiscoveryMode] = useState("");

  // Store original values to detect changes
  const [originalValues, setOriginalValues] = useState<{
    ipv4: string;
    ipv6: string;
    hostname: string;
    hostnameFromDHCP: boolean;
    discoveryMode: string;
  }>({
    ipv4: "",
    ipv6: "",
    hostname: "",
    hostnameFromDHCP: false,
    discoveryMode: "",
  });

  // Sync hostnameFromDHCP state with API data
  useEffect(() => {
    if (hostnameData?.hostname) {
      const hostnameFromData = hostnameData.hostname;
      if (typeof hostnameFromData === "object" && hostnameFromData !== null) {
        const fromDHCP = (hostnameFromData as { FromDHCP?: boolean }).FromDHCP;
        if (fromDHCP !== undefined) {
          setHostnameFromDHCP(fromDHCP);
        }
      }
    }
  }, [hostnameData]);

  // Data extraction for display
  if (networkGatewayData && typeof networkGatewayData === "object") {
    if (Array.isArray(networkGatewayData.IPv4Address)) {
      networkGatewayData.IPv4Address.forEach((ipv4, idx) => {
        if (ipv4) {
          networkSettingsItems.push({
            label:
              networkGatewayData.IPv4Address!.length > 1
                ? `IPv4 Gateway (#${idx + 1})`
                : "IPv4 Gateway",
            value: ipv4,
          });
        }
      });
    }
    if (Array.isArray(networkGatewayData.IPv6Address)) {
      networkGatewayData.IPv6Address.forEach((ipv6, idx) => {
        if (ipv6) {
          networkSettingsItems.push({
            label:
              networkGatewayData.IPv6Address!.length > 1
                ? `IPv6 Gateway (#${idx + 1})`
                : "IPv6 Gateway",
            value: ipv6,
          });
        }
      });
    }
  }

  if (hostnameData?.hostname) {
    const hostnameFromData = hostnameData.hostname;
    if (typeof hostnameFromData === "object" && hostnameFromData !== null) {
      const hostnameName = (hostnameFromData as { Name?: string }).Name;
      const fromDHCP = (hostnameFromData as { FromDHCP?: boolean }).FromDHCP;

      if (hostnameName) {
        networkSettingsItems.push({
          label: "Hostname",
          value: hostnameName,
        });
      }

      if (fromDHCP !== undefined) {
        networkSettingsItems.push({
          label: "Hostname DHCP",
          value: fromDHCP ? "Enabled" : "Disabled",
        });
      }
    } else if (typeof hostnameFromData === "string") {
      networkSettingsItems.push({ label: "Hostname", value: hostnameFromData });
    }
  }

  if (isDiscoveryNotSupported) {
    networkSettingsItems.push({
      label: "Discovery Mode",
      value: "Not Supported",
    });
  } else if (discoveryData?.discovery_mode) {
    networkSettingsItems.push({
      label: "Discovery Mode",
      value: discoveryData.discovery_mode,
    });
  }

  // Handlers
  const handleEditGateway = () => {
    let ipv4 = "";
    let ipv6 = "";

    if (networkGatewayData) {
      if (
        networkGatewayData.IPv4Address &&
        networkGatewayData.IPv4Address.length > 0
      ) {
        ipv4 = networkGatewayData.IPv4Address[0];
        setIpv4Address(ipv4);
        setIpVersion("ipv4");
      } else if (
        networkGatewayData.IPv6Address &&
        networkGatewayData.IPv6Address.length > 0
      ) {
        ipv6 = networkGatewayData.IPv6Address[0];
        setIpv6Address(ipv6);
        setIpVersion("ipv6");
      } else {
        setIpv4Address("");
        setIpv6Address("");
        setIpVersion("ipv4");
      }
    }

    // Pre-fill hostname
    let hostnameValue = "";
    if (hostnameData?.hostname) {
      const hostnameObj = hostnameData.hostname;
      if (typeof hostnameObj === "object" && hostnameObj !== null) {
        hostnameValue = (hostnameObj as { Name?: string }).Name || "";
      } else if (typeof hostnameObj === "string") {
        hostnameValue = hostnameObj;
      }
    }
    setHostname(hostnameValue);

    // Pre-fill discovery mode
    const discoveryModeValue = discoveryData?.discovery_mode || "";
    setDiscoveryMode(discoveryModeValue);

    // Store original values
    setOriginalValues({
      ipv4,
      ipv6,
      hostname: hostnameValue,
      hostnameFromDHCP,
      discoveryMode: discoveryModeValue,
    });

    setDialogOpen(true);
  };

  // Check if there are any changes
  const currentValues = {
    ipv4: ipVersion === "ipv4" ? ipv4Address : "",
    ipv6: ipVersion === "ipv6" ? ipv6Address : "",
    hostname,
    hostnameFromDHCP,
    discoveryMode,
  };

  const hasChanges = useFormChanges(currentValues, originalValues);

  // Check if gateway address is valid when gateway settings changed
  const currentIpv4 = ipVersion === "ipv4" ? ipv4Address : "";
  const currentIpv6 = ipVersion === "ipv6" ? ipv6Address : "";
  const isGatewayChanged =
    currentIpv4 !== originalValues.ipv4 || currentIpv6 !== originalValues.ipv6;
  const isGatewayAddressEmpty =
    ipVersion === "ipv4" ? !ipv4Address.trim() : !ipv6Address.trim();
  const isGatewayInvalid = isGatewayChanged && isGatewayAddressEmpty;

  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  const handleSave = async () => {
    try {
      const promises = [];

      // Check if gateway changed
      if (isGatewayChanged) {
        promises.push(
          setNetworkGatewayMutation.mutateAsync({
            ipv4_address: currentIpv4 || undefined,
            ipv6_address: currentIpv6 || undefined,
          }),
        );
      }

      // Check if hostname changed
      if (hostname !== originalValues.hostname && hostname.trim()) {
        promises.push(setHostnameMutation.mutateAsync(hostname.trim()));
      }

      // Check if hostname from DHCP changed (only if supported)
      if (
        isHostnameFromDHCPSupported &&
        hostnameFromDHCP !== originalValues.hostnameFromDHCP
      ) {
        promises.push(
          setHostnameFromDHCPMutation.mutateAsync(hostnameFromDHCP),
        );
      }

      // Check if discovery mode changed (only if discovery is supported)
      if (
        !isDiscoveryNotSupported &&
        discoveryMode !== originalValues.discoveryMode &&
        discoveryMode.trim()
      ) {
        const discoverable = discoveryMode === "Discoverable";
        promises.push(setDiscoveryModeMutation.mutateAsync(discoverable));
      }

      if (promises.length > 0) {
        await Promise.all(promises);
        toast.success("Network settings updated successfully");
        handleDialogClose();
      } else {
        toast.info("No changes to save");
        handleDialogClose();
      }
    } catch (err) {
      toast.error("Failed to update network settings");
    }
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load device network settings"}
      isEmpty={networkSettingsItems.length === 0}
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
            onClick={handleEditGateway}
            disabled={isNetworkConfigNotSupported}
          >
            Configure
          </Button>
        </Box>

        {/* Network Settings Table */}
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
              {networkSettingsItems
                .filter((item) => item.value)
                .map((item) => (
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

        {/* Configure Network Settings Dialog */}
        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Configure Network Settings</DialogTitle>
          <DialogContent>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
            >
              <Box>
                <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
                  <FormControl sx={{ minWidth: 120 }}>
                    <InputLabel>IP Version</InputLabel>
                    <Select
                      value={ipVersion}
                      label="IP Version"
                      onChange={(e) =>
                        setIpVersion(e.target.value as "ipv4" | "ipv6")
                      }
                    >
                      <MenuItem value="ipv4">IPv4</MenuItem>
                      <MenuItem value="ipv6">IPv6</MenuItem>
                    </Select>
                  </FormControl>

                  {ipVersion === "ipv4" ? (
                    <TextField
                      fullWidth
                      label="Gateway Address"
                      value={ipv4Address}
                      onChange={(e) => setIpv4Address(e.target.value)}
                      placeholder="e.g., 192.168.1.1"
                    />
                  ) : (
                    <TextField
                      fullWidth
                      label="Gateway Address"
                      value={ipv6Address}
                      onChange={(e) => setIpv6Address(e.target.value)}
                      placeholder="e.g., fe80::1"
                    />
                  )}
                </Box>
                <FormHelperText sx={{ pl: 1.8 }}>
                  Set the network default gateway address.
                </FormHelperText>
              </Box>
              <Box>
                <Box
                  sx={{
                    display: "flex",
                    gap: 2,
                    alignItems: "center",
                  }}
                >
                  <FormControl sx={{ minWidth: 120 }}>
                    <InputLabel>From DHCP</InputLabel>
                    <Select
                      value={hostnameFromDHCP ? "Enabled" : "Disabled"}
                      label="From DHCP"
                      disabled={!isHostnameFromDHCPSupported}
                      onChange={(e) =>
                        setHostnameFromDHCP(e.target.value === "Enabled")
                      }
                    >
                      <MenuItem value="Enabled">Enabled</MenuItem>
                      <MenuItem value="Disabled">Disabled</MenuItem>
                    </Select>
                  </FormControl>
                  <TextField
                    fullWidth
                    label="Hostname"
                    value={hostname}
                    onChange={(e) => setHostname(e.target.value)}
                    placeholder="Enter device hostname"
                  />
                </Box>
                <FormHelperText sx={{ pl: 1.8 }}>
                  Set the network hostname for this device.
                </FormHelperText>
              </Box>

              <FormControl fullWidth disabled={isDiscoveryNotSupported}>
                <InputLabel>Discovery Mode</InputLabel>
                <Select
                  value={isDiscoveryNotSupported ? "" : discoveryMode}
                  label="Discovery Mode"
                  onChange={(e) => setDiscoveryMode(e.target.value)}
                >
                  <MenuItem value="Discoverable">Discoverable</MenuItem>
                  <MenuItem value="NonDiscoverable">Non-Discoverable</MenuItem>
                </Select>
                <FormHelperText>
                  {isDiscoveryNotSupported
                    ? "Discovery mode configuration is not supported by this device."
                    : "Set the device discoverability on the network via WS-Discovery."}
                </FormHelperText>
              </FormControl>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Cancel</Button>
            <Button
              onClick={handleSave}
              variant="contained"
              disabled={
                !hasChanges ||
                isGatewayInvalid ||
                setNetworkGatewayMutation.isPending ||
                setHostnameMutation.isPending ||
                setHostnameFromDHCPMutation.isPending ||
                setDiscoveryModeMutation.isPending
              }
            >
              {setNetworkGatewayMutation.isPending ||
              setHostnameMutation.isPending ||
              setHostnameFromDHCPMutation.isPending ||
              setDiscoveryModeMutation.isPending ? (
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
