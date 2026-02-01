import { AddAlt, GlobalFilters, Help, TrashCan } from "@carbon/icons-react";
import {
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
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
import { useCallback, useEffect, useRef, useState } from "react";

import { useToast } from "hooks/UseToast";
import { useFormChanges } from "hooks/useFormChanges";
import {
  useGetDeviceNetworkInterfaces,
  useSetDeviceNetworkInterfaces,
} from "lib/api/actions/onvif/device";

import { QueryWrapper } from "../../config/QueryWrapper";

interface DeviceNetworkInterfacesProps {
  cameraIdentifier: string;
  deviceCapabilities?: any;
}

// Helper to format MAC address (a8-29-48-33-fe-3c -> A8:29:48:33:FE:3C)
const formatMacAddress = (mac: string): string =>
  mac.toUpperCase().replace(/-/g, ":");

export function DeviceNetworkInterfaces({
  cameraIdentifier,
  deviceCapabilities,
}: DeviceNetworkInterfacesProps) {
  // Check if network configuration is not supported
  const isNetworkConfigNotSupported =
    deviceCapabilities?.System?.NetworkConfigNotSupported === true;

  const TITLE = "Network Interfaces";
  const DESC =
    "Manage network interfaces for this device. Some cameras will 'perform' or 'require' a reboot after this configuration is changed.";

  const theme = useTheme();
  const toast = useToast();

  // ONVIF API hooks
  const { data, isLoading, isError, error } = useGetDeviceNetworkInterfaces(
    cameraIdentifier,
    !isNetworkConfigNotSupported,
  );
  const setNetworkInterfacesMutation =
    useSetDeviceNetworkInterfaces(cameraIdentifier);

  const interfaces = data?.network_interfaces;

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedInterfaceToken, setSelectedInterfaceToken] = useState("");
  const [interfaceEnabled, setInterfaceEnabled] = useState(true);
  const [mtu, setMtu] = useState<number | "">("");
  const [linkAutoNegotiation, setLinkAutoNegotiation] = useState(true);
  const [linkSpeed, setLinkSpeed] = useState<number | "">(100);
  const [linkDuplex, setLinkDuplex] = useState<"Full" | "Half">("Full");
  const [ipv4Enabled, setIpv4Enabled] = useState(true);
  const [ipv4DHCP, setIpv4DHCP] = useState(true);
  const [ipv4ManualAddresses, setIpv4ManualAddresses] = useState<
    { id: string; address: string; prefixLength: number | "" }[]
  >([]);
  const [ipv6Enabled, setIpv6Enabled] = useState(true);
  const [ipv6AcceptRouterAdvert, setIpv6AcceptRouterAdvert] = useState(false);
  const [ipv6DHCP, setIpv6DHCP] = useState<
    "Auto" | "Stateful" | "Stateless" | "Off"
  >("Auto");
  const [ipv6ManualAddresses, setIpv6ManualAddresses] = useState<
    { id: string; address: string; prefixLength: number | "" }[]
  >([]);
  const [originalValues, setOriginalValues] = useState<any>({});

  const addressIdCounterRef = useRef(0);
  const generateAddressId = useCallback(
    () => `address-${++addressIdCounterRef.current}`,
    [],
  );

  // Get selected interface data
  const selectedInterface = interfaces?.find(
    (iface: any) => iface.token === selectedInterfaceToken,
  );

  // Handlers
  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  const loadInterfaceData = useCallback(
    (iface: any) => {
      const token = iface.token;
      const enabled = iface.Enabled ?? true;
      const mtuValue = iface.Info?.MTU ?? "";

      // Link settings (use AdminSettings for configuration)
      const linkAutoNeg = iface.Link?.AdminSettings?.AutoNegotiation ?? true;
      const linkSpd = iface.Link?.AdminSettings?.Speed ?? 100;
      const linkDup = iface.Link?.AdminSettings?.Duplex ?? "Full";

      // IPv4 settings
      const ipv4En = iface.IPv4?.Enabled ?? true;
      const ipv4Dhcp = iface.IPv4?.Config?.DHCP ?? true;
      const ipv4Manual =
        iface.IPv4?.Config?.Manual?.map((addr: any) => ({
          id: generateAddressId(),
          address: addr.Address ?? "",
          prefixLength: addr.PrefixLength ?? "",
        })) ?? [];

      // IPv6 settings
      const ipv6En = iface.IPv6?.Enabled ?? true;
      const ipv6AcceptRA = iface.IPv6?.Config?.AcceptRouterAdvert ?? false;
      const ipv6Dhcp = iface.IPv6?.Config?.DHCP ?? "Auto";
      const ipv6Manual =
        iface.IPv6?.Config?.Manual?.map((addr: any) => ({
          id: generateAddressId(),
          address: addr.Address ?? "",
          prefixLength: addr.PrefixLength ?? "",
        })) ?? [];

      setSelectedInterfaceToken(token);
      setInterfaceEnabled(enabled);
      setMtu(mtuValue);
      setLinkAutoNegotiation(linkAutoNeg);
      setLinkSpeed(linkSpd);
      setLinkDuplex(linkDup);
      setIpv4Enabled(ipv4En);
      setIpv4DHCP(ipv4Dhcp);
      setIpv4ManualAddresses(ipv4Manual);
      setIpv6Enabled(ipv6En);
      setIpv6AcceptRouterAdvert(ipv6AcceptRA);
      setIpv6DHCP(ipv6Dhcp);
      setIpv6ManualAddresses(ipv6Manual);

      setOriginalValues({
        selectedInterfaceToken: token,
        interfaceEnabled: enabled,
        mtu: mtuValue,
        linkAutoNegotiation: linkAutoNeg,
        linkSpeed: linkSpd,
        linkDuplex: linkDup,
        ipv4Enabled: ipv4En,
        ipv4DHCP: ipv4Dhcp,
        ipv4ManualAddresses: ipv4Manual,
        ipv6Enabled: ipv6En,
        ipv6AcceptRouterAdvert: ipv6AcceptRA,
        ipv6DHCP: ipv6Dhcp,
        ipv6ManualAddresses: ipv6Manual,
      });
    },
    [generateAddressId], // Empty deps since generateAddressId is stable and setters are stable
  );

  const handleOpenDialog = () => {
    // Default to first interface
    const firstInterface = interfaces?.[0];
    if (!firstInterface) return;

    loadInterfaceData(firstInterface);
    setDialogOpen(true);
  };

  // Handle interface selection change
  useEffect(() => {
    if (selectedInterfaceToken && selectedInterface) {
      loadInterfaceData(selectedInterface);
    }
  }, [selectedInterfaceToken, selectedInterface, loadInterfaceData]);

  // IPv4 manual address handlers
  const handleAddIpv4Address = () => {
    setIpv4ManualAddresses([
      ...ipv4ManualAddresses,
      { id: generateAddressId(), address: "", prefixLength: "" },
    ]);
  };

  const handleRemoveIpv4Address = (index: number) => {
    setIpv4ManualAddresses(ipv4ManualAddresses.filter((_, i) => i !== index));
  };

  const handleIpv4AddressChange = (
    index: number,
    field: "address" | "prefixLength",
    value: string | number,
  ) => {
    const updated = ipv4ManualAddresses.map((addr, i) =>
      i === index ? { ...addr, [field]: value } : addr,
    );
    setIpv4ManualAddresses(updated);
  };

  // IPv6 manual address handlers
  const handleAddIpv6Address = () => {
    setIpv6ManualAddresses([
      ...ipv6ManualAddresses,
      { id: generateAddressId(), address: "", prefixLength: "" },
    ]);
  };

  const handleRemoveIpv6Address = (index: number) => {
    setIpv6ManualAddresses(ipv6ManualAddresses.filter((_, i) => i !== index));
  };

  const handleIpv6AddressChange = (
    index: number,
    field: "address" | "prefixLength",
    value: string | number,
  ) => {
    const updated = ipv6ManualAddresses.map((addr, i) =>
      i === index ? { ...addr, [field]: value } : addr,
    );
    setIpv6ManualAddresses(updated);
  };

  // Check if there are any changes
  const hasChanges = useFormChanges(
    {
      selectedInterfaceToken,
      interfaceEnabled,
      mtu,
      linkAutoNegotiation,
      linkSpeed,
      linkDuplex,
      ipv4Enabled,
      ipv4DHCP,
      ipv4ManualAddresses,
      ipv6Enabled,
      ipv6AcceptRouterAdvert,
      ipv6DHCP,
      ipv6ManualAddresses,
    },
    originalValues,
    {
      ipv4ManualAddresses: (current: any[], original: any[]) => {
        if (current.length !== original.length) return false;
        return current.every(
          (addr, i) =>
            addr.address === original[i]?.address &&
            addr.prefixLength === original[i]?.prefixLength,
        );
      },
      ipv6ManualAddresses: (current: any[], original: any[]) => {
        if (current.length !== original.length) return false;
        return current.every(
          (addr, i) =>
            addr.address === original[i]?.address &&
            addr.prefixLength === original[i]?.prefixLength,
        );
      },
    },
  );

  const handleUpdateNetworkInterface = () => {
    // Build IPv4 configuration (only if device supports IPv4)
    const ipv4Config =
      selectedInterface?.IPv4 && ipv4Enabled
        ? {
            Enabled: ipv4Enabled,
            DHCP: ipv4DHCP,
            Manual:
              !ipv4DHCP && ipv4ManualAddresses.length > 0
                ? ipv4ManualAddresses
                    .filter((addr) => addr.address.trim())
                    .map((addr) => ({
                      Address: addr.address.trim(),
                      PrefixLength: Number(addr.prefixLength) || 24,
                    }))
                : undefined,
          }
        : undefined;

    // Build IPv6 configuration (only if device supports IPv6)
    const ipv6Config =
      selectedInterface?.IPv6 && ipv6Enabled
        ? {
            Enabled: ipv6Enabled,
            AcceptRouterAdvert: ipv6AcceptRouterAdvert,
            DHCP: ipv6DHCP,
            Manual:
              ipv6DHCP === "Off" && ipv6ManualAddresses.length > 0
                ? ipv6ManualAddresses
                    .filter((addr) => addr.address.trim())
                    .map((addr) => ({
                      Address: addr.address.trim(),
                      PrefixLength: Number(addr.prefixLength) || 64,
                    }))
                : undefined,
          }
        : undefined;

    // Build network interface configuration
    const networkInterface: any = {
      Enabled: interfaceEnabled,
    };

    if (mtu !== "") {
      networkInterface.MTU = Number(mtu);
    }

    if (selectedInterface?.Link?.AdminSettings) {
      networkInterface.Link = {
        AutoNegotiation: linkAutoNegotiation,
        Speed: Number(linkSpeed) || 100,
        Duplex: linkDuplex,
      };
    }

    if (ipv4Config) {
      networkInterface.IPv4 = ipv4Config;
    }

    if (ipv6Config) {
      networkInterface.IPv6 = ipv6Config;
    }

    setNetworkInterfacesMutation.mutate(
      {
        interface_token: selectedInterfaceToken,
        network_interface: networkInterface,
      },
      {
        onSuccess: () => {
          toast.success("Network interface updated successfully");
          setDialogOpen(false);
        },
        onError: () => {
          toast.error("Failed to update network interface");
        },
      },
    );
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={
        error?.message || "Failed to load device network interfaces"
      }
      isEmpty={!interfaces || interfaces.length === 0}
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
        <Box rowGap={3} display="flex" flexDirection="column">
          {interfaces?.map(
            (iface: {
              token: string;
              Enabled: boolean;
              Info?: { Name?: string; HwAddress: string; MTU?: number };
              Link?: {
                AdminSettings?: {
                  AutoNegotiation: boolean;
                  Speed: number;
                  Duplex: "Full" | "Half";
                };
                OperSettings?: {
                  AutoNegotiation: boolean;
                  Speed: number;
                  Duplex: "Full" | "Half";
                };
                InterfaceType?: number;
              };
              IPv4?: {
                Enabled: boolean;
                Config: {
                  DHCP: boolean;
                  Manual?: { Address?: string; PrefixLength?: number }[];
                  LinkLocal?: { Address?: string; PrefixLength?: number };
                  FromDHCP?: { Address?: string; PrefixLength?: number };
                };
              };
              IPv6?: {
                Enabled: boolean;
                Config?: {
                  AcceptRouterAdvert?: boolean;
                  DHCP: "Auto" | "Stateful" | "Stateless" | "Off";
                  Manual: { Address?: string; PrefixLength?: number }[];
                  LinkLocal: { Address?: string; PrefixLength?: number }[];
                  FromDHCP: { Address?: string; PrefixLength?: number }[];
                  FromRA: { Address?: string; PrefixLength?: number }[];
                };
              };
            }) => {
              const infoItems: { label: string; value: string }[] = [];

              // General Information
              infoItems.push({
                label: "Status",
                value: iface.Enabled ? "Enabled" : "Disabled",
              });
              if (iface.Info?.Name) {
                infoItems.push({ label: "Interface", value: iface.Info.Name });
              }
              if (iface.Info?.HwAddress) {
                infoItems.push({
                  label: "MAC Address",
                  value: formatMacAddress(iface.Info.HwAddress),
                });
              }
              if (iface.Info?.MTU) {
                infoItems.push({ label: "MTU", value: String(iface.Info.MTU) });
              }

              // Link Information (show OperSettings - current active settings)
              if (iface.Link?.OperSettings) {
                if (iface.Link?.OperSettings?.AutoNegotiation) {
                  infoItems.push({
                    label: "Auto-Nego",
                    value: iface.Link.OperSettings.AutoNegotiation
                      ? "Enabled"
                      : "Disabled",
                  });
                }
                if (iface.Link?.OperSettings?.Speed) {
                  infoItems.push({
                    label: "Speed",
                    value: `${iface.Link.OperSettings.Speed} Mbps`,
                  });
                }
                if (iface.Link?.OperSettings?.Duplex) {
                  infoItems.push({
                    label: "Duplex Mode",
                    value: `${iface.Link.OperSettings.Duplex} Duplex`,
                  });
                }
              }

              // IPv4 Information
              if (iface.IPv4) {
                infoItems.push({
                  label: "IPv4 Status",
                  value: iface.IPv4.Enabled ? "Enabled" : "Disabled",
                });
                if (iface.IPv4.Config) {
                  const dhcpEnabled = iface.IPv4.Config.DHCP === true;
                  infoItems.push({
                    label: "IPv4 DHCP",
                    value: dhcpEnabled ? "Enabled" : "Disabled",
                  });
                }
                if (
                  iface.IPv4.Config.Manual &&
                  iface.IPv4.Config.Manual.length > 0
                ) {
                  infoItems.push({
                    label: "IPv4 Address",
                    value: iface.IPv4.Config.Manual?.map(
                      (addr) =>
                        `${addr.Address ?? "N/A"}/${
                          addr.PrefixLength ?? "N/A"
                        }`,
                    ).join(", "),
                  });
                }
                if (iface.IPv4.Config.LinkLocal) {
                  infoItems.push({
                    label: "IPv4 Address",
                    value: `${iface.IPv4.Config.LinkLocal.Address ?? "N/A"}/${iface.IPv4.Config.LinkLocal.PrefixLength ?? "N/A"}`,
                  });
                }
                if (iface.IPv4.Config.FromDHCP) {
                  infoItems.push({
                    label: "IPv4 Address",
                    value: `${iface.IPv4.Config.FromDHCP.Address ?? "N/A"}/${iface.IPv4.Config.FromDHCP.PrefixLength ?? "N/A"}`,
                  });
                }
              }

              // IPv6 Information
              if (iface.IPv6) {
                infoItems.push({
                  label: "IPv6 Status",
                  value: iface.IPv6.Enabled ? "Enabled" : "Disabled",
                });
                if (iface.IPv6.Config) {
                  infoItems.push({
                    label: "IPv6 DHCP",
                    value: iface.IPv6.Config.DHCP,
                  });
                  if (iface.IPv6.Config?.Manual.length > 0) {
                    infoItems.push({
                      label: "IPv6 Address",
                      value: iface.IPv6.Config.Manual?.map(
                        (addr) =>
                          `${addr.Address ?? "N/A"}/${
                            addr.PrefixLength ?? "N/A"
                          }`,
                      ).join(", "),
                    });
                  }
                  if (iface.IPv6.Config?.LinkLocal.length > 0) {
                    infoItems.push({
                      label: "IPv6 Address",
                      value: iface.IPv6.Config.LinkLocal?.map(
                        (addr) =>
                          `${addr.Address ?? "N/A"}/${
                            addr.PrefixLength ?? "N/A"
                          }`,
                      ).join(", "),
                    });
                  }
                  if (iface.IPv6.Config?.FromDHCP.length > 0) {
                    infoItems.push({
                      label: "IPv6 Address",
                      value: iface.IPv6.Config.FromDHCP?.map(
                        (addr) =>
                          `${addr.Address ?? "N/A"}/${
                            addr.PrefixLength ?? "N/A"
                          }`,
                      ).join(", "),
                    });
                  }
                  if (iface.IPv6.Config?.FromRA.length > 0) {
                    infoItems.push({
                      label: "IPv6 Address",
                      value: iface.IPv6.Config.FromRA?.map(
                        (addr) =>
                          `${addr.Address ?? "N/A"}/${
                            addr.PrefixLength ?? "N/A"
                          }`,
                      ).join(", "),
                    });
                  }
                }
              }

              // Token
              infoItems.push({
                label: "Token",
                value: iface.token,
              });

              return (
                <TableContainer key={iface.token}>
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
                            <Typography variant="body2">
                              {item.label}
                            </Typography>
                          </TableCell>
                          <TableCell sx={{ py: 1, pr: 0 }}>
                            <Typography variant="body2">
                              {item.value}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              );
            },
          )}
        </Box>

        {/* Network Interface Configuration Dialog */}
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
                Configure Network Interfaces
              </Typography>
              <Typography variant="caption" fontWeight="medium" color="primary">
                {selectedInterface?.token || "Network Interface"}
              </Typography>
            </Box>
          </DialogTitle>
          <DialogContent>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
            >
              {/* Interface Selection */}
              <Box>
                <Box
                  sx={{
                    display: "flex",
                    gap: 2,
                    alignItems: "center",
                  }}
                >
                  <FormControl fullWidth>
                    <InputLabel>Selected Interface</InputLabel>
                    <Select
                      value={selectedInterfaceToken}
                      onChange={(e) =>
                        setSelectedInterfaceToken(e.target.value)
                      }
                      label="Selected Interface"
                    >
                      {interfaces?.map((iface: any) => (
                        <MenuItem key={iface.token} value={iface.token}>
                          {iface.Info?.Name || iface.token} (
                          {iface.Info?.HwAddress
                            ? formatMacAddress(iface.Info.HwAddress)
                            : "No MAC"}
                          )
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl sx={{ minWidth: 120 }}>
                    <InputLabel>Status</InputLabel>
                    <Select
                      value={interfaceEnabled ? "Enabled" : "Disabled"}
                      label="Status"
                      onChange={(e) =>
                        setInterfaceEnabled(e.target.value === "Enabled")
                      }
                    >
                      <MenuItem value="Enabled">Enabled</MenuItem>
                      <MenuItem value="Disabled">Disabled</MenuItem>
                    </Select>
                  </FormControl>
                </Box>
              </Box>

              {/* General Settings */}
              <TextField
                fullWidth
                label="MTU (Maximum Transmission Unit)"
                type="number"
                value={mtu}
                onChange={(e) =>
                  setMtu(e.target.value ? Number(e.target.value) : "")
                }
                helperText="Leave empty to use default value."
              />

              {/* Link Configuration */}
              {selectedInterface?.Link?.AdminSettings && (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Link Configuration{" "}
                    <Typography variant="caption" gutterBottom>
                      (some cameras ignore this!)
                    </Typography>
                  </Typography>
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 2,
                      mt: 2,
                    }}
                  >
                    <Box
                      sx={{
                        display: "flex",
                        gap: 2,
                        alignItems: "center",
                      }}
                    >
                      <FormControl fullWidth>
                        <InputLabel>Auto Negotiation</InputLabel>
                        <Select
                          value={linkAutoNegotiation ? "Enabled" : "Disabled"}
                          label="Auto Negotiation"
                          onChange={(e) =>
                            setLinkAutoNegotiation(e.target.value === "Enabled")
                          }
                        >
                          <MenuItem value="Enabled">Enabled</MenuItem>
                          <MenuItem value="Disabled">Disabled</MenuItem>
                        </Select>
                      </FormControl>
                      <FormControl fullWidth>
                        <InputLabel>Duplex Mode</InputLabel>
                        <Select
                          value={linkDuplex}
                          onChange={(e) =>
                            setLinkDuplex(e.target.value as "Full" | "Half")
                          }
                          label="Duplex Mode"
                        >
                          <MenuItem value="Full">Full Duplex</MenuItem>
                          <MenuItem value="Half">Half Duplex</MenuItem>
                        </Select>
                      </FormControl>
                    </Box>

                    <TextField
                      fullWidth
                      label="Speed (Mbps)"
                      type="number"
                      value={linkSpeed}
                      onChange={(e) =>
                        setLinkSpeed(
                          e.target.value ? Number(e.target.value) : "",
                        )
                      }
                      placeholder="100"
                      helperText="Common values: 10, 100, 1000"
                    />
                  </Box>
                </Box>
              )}

              {/* IPv4 Settings */}
              {selectedInterface?.IPv4 && (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    IPv4 Configuration
                  </Typography>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={ipv4Enabled}
                        onChange={(e) => setIpv4Enabled(e.target.checked)}
                      />
                    }
                    label="IPv4 Enabled"
                  />
                  {ipv4Enabled && (
                    <>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={ipv4DHCP}
                            onChange={(e) => setIpv4DHCP(e.target.checked)}
                          />
                        }
                        label="Use DHCP"
                      />
                      {!ipv4DHCP && (
                        <Box
                          sx={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 2,
                            mt: 1,
                          }}
                        >
                          {ipv4ManualAddresses.map((addr, index) => (
                            <Stack
                              key={addr.id}
                              direction="row"
                              spacing={2}
                              alignItems="center"
                            >
                              <TextField
                                fullWidth
                                label="IPv4 Address"
                                value={addr.address}
                                onChange={(e) =>
                                  handleIpv4AddressChange(
                                    index,
                                    "address",
                                    e.target.value,
                                  )
                                }
                                placeholder="192.168.1.100"
                              />
                              <TextField
                                label="Prefix"
                                type="number"
                                value={addr.prefixLength}
                                onChange={(e) =>
                                  handleIpv4AddressChange(
                                    index,
                                    "prefixLength",
                                    e.target.value
                                      ? Number(e.target.value)
                                      : "",
                                  )
                                }
                                sx={{ width: 120 }}
                                placeholder="24"
                              />
                              <IconButton
                                size="small"
                                onClick={() => handleRemoveIpv4Address(index)}
                                disabled={ipv4ManualAddresses.length === 1}
                                color="error"
                              >
                                <TrashCan size={20} />
                              </IconButton>
                            </Stack>
                          ))}
                          <Button
                            startIcon={<AddAlt size={16} />}
                            onClick={handleAddIpv4Address}
                            variant="outlined"
                          >
                            Add Address
                          </Button>
                        </Box>
                      )}
                    </>
                  )}
                </Box>
              )}

              {/* IPv6 Settings */}
              {selectedInterface?.IPv6 && (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    IPv6 Configuration
                  </Typography>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={ipv6Enabled}
                        onChange={(e) => setIpv6Enabled(e.target.checked)}
                      />
                    }
                    label="IPv6 Enabled"
                  />
                  {ipv6Enabled && (
                    <>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={ipv6AcceptRouterAdvert}
                            onChange={(e) =>
                              setIpv6AcceptRouterAdvert(e.target.checked)
                            }
                          />
                        }
                        label="Accept Router Advertisement"
                      />
                      <FormControl fullWidth sx={{ mt: 1, mb: 1 }}>
                        <InputLabel>DHCP Mode</InputLabel>
                        <Select
                          value={ipv6DHCP}
                          onChange={(e) =>
                            setIpv6DHCP(
                              e.target.value as
                                | "Auto"
                                | "Stateful"
                                | "Stateless"
                                | "Off",
                            )
                          }
                          label="DHCP Mode"
                        >
                          <MenuItem value="Auto">Auto</MenuItem>
                          <MenuItem value="Stateful">Stateful</MenuItem>
                          <MenuItem value="Stateless">Stateless</MenuItem>
                          <MenuItem value="Off">Off</MenuItem>
                        </Select>
                      </FormControl>
                      {ipv6DHCP === "Off" && (
                        <Box
                          sx={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 2,
                            mt: 1,
                          }}
                        >
                          {ipv6ManualAddresses.map((addr, index) => (
                            <Stack
                              key={addr.id}
                              direction="row"
                              spacing={2}
                              alignItems="center"
                            >
                              <TextField
                                fullWidth
                                label="IPv6 Address"
                                value={addr.address}
                                onChange={(e) =>
                                  handleIpv6AddressChange(
                                    index,
                                    "address",
                                    e.target.value,
                                  )
                                }
                                placeholder="2001:db8::1"
                              />
                              <TextField
                                label="Prefix"
                                type="number"
                                value={addr.prefixLength}
                                onChange={(e) =>
                                  handleIpv6AddressChange(
                                    index,
                                    "prefixLength",
                                    e.target.value
                                      ? Number(e.target.value)
                                      : "",
                                  )
                                }
                                sx={{ width: 120 }}
                                placeholder="64"
                              />
                              <IconButton
                                onClick={() => handleRemoveIpv6Address(index)}
                                disabled={ipv6ManualAddresses.length === 1}
                                color="error"
                              >
                                <TrashCan size={20} />
                              </IconButton>
                            </Stack>
                          ))}
                          <Button
                            startIcon={<AddAlt size={16} />}
                            onClick={handleAddIpv6Address}
                            variant="outlined"
                          >
                            Add Address
                          </Button>
                        </Box>
                      )}
                    </>
                  )}
                </Box>
              )}
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Cancel</Button>
            <Button
              onClick={handleUpdateNetworkInterface}
              variant="contained"
              disabled={
                setNetworkInterfacesMutation.isPending ||
                !hasChanges ||
                !selectedInterfaceToken
              }
            >
              {setNetworkInterfacesMutation.isPending ? (
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
