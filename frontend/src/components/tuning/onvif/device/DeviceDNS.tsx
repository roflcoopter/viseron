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
import { useGetDeviceDNS, useSetDeviceDNS } from "lib/api/actions/onvif/device";

import { QueryWrapper } from "../../config/QueryWrapper";

type DNSType = "IPv4" | "IPv6" | "";

interface DNSServerEntry {
  id: string;
  type: DNSType;
  server: string;
}

interface SearchDomainEntry {
  id: string;
  domain: string;
}

let dnsServerIdCounter = 0;
const generateDnsServerId = () => `dns-server-${++dnsServerIdCounter}`;

let searchDomainIdCounter = 0;
const generateSearchDomainId = () => `search-domain-${++searchDomainIdCounter}`;

interface DeviceDNSProps {
  cameraIdentifier: string;
  deviceCapabilities?: any;
}

export function DeviceDNS({
  cameraIdentifier,
  deviceCapabilities,
}: DeviceDNSProps) {
  // Check if network configuration is not supported
  const isNetworkConfigNotSupported =
    deviceCapabilities?.System?.NetworkConfigNotSupported === true;

  const TITLE = "DNS Settings";
  const DESC =
    "Manage Domain Name System (DNS) settings for the device. Changes to the 'DNS Servers' and 'Search Domains' lists will be ignored if 'DNS From DHCP' is enabled.";

  const theme = useTheme();
  const toast = useToast();

  // ONVIF API hooks
  const { data, isLoading, isError, error } = useGetDeviceDNS(
    cameraIdentifier,
    !isNetworkConfigNotSupported,
  );
  const setDNSMutation = useSetDeviceDNS(cameraIdentifier);

  const dns = data?.dns;
  const infoItems: { label: string; value: string }[] = [];

  // Section state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [DNSFromDHCP, setDNSFromDHCP] = useState<boolean>(false);
  const [searchDomains, setSearchDomains] = useState<SearchDomainEntry[]>([]);
  const [dnsServers, setDnsServers] = useState<DNSServerEntry[]>([]);
  const [originalValues, setOriginalValues] = useState<{
    DNSFromDHCP: boolean;
    searchDomains: SearchDomainEntry[];
    dnsServers: DNSServerEntry[];
  }>({
    DNSFromDHCP: false,
    searchDomains: [],
    dnsServers: [],
  });

  // Data extraction for display
  if (dns) {
    if (dns.FromDHCP !== undefined) {
      infoItems.push({
        label: "From DHCP",
        value: dns.FromDHCP ? "Enabled" : "Disabled",
      });
    }

    // Add search domains
    if (dns.SearchDomain && dns.SearchDomain.length > 0) {
      dns.SearchDomain.forEach((domain: string, index: number) => {
        infoItems.push({
          label: `Domain (#${index + 1})`,
          value: domain,
        });
      });
    }

    // Add DNS servers
    const addDnsServers = (servers?: Array<Record<string, any>>) => {
      if (!servers?.length) {
        return false;
      }

      let hasValidServer = false;

      servers.forEach((server, index) => {
        const hasIPv4 = server?.IPv4Address;
        const hasIPv6 = server?.IPv6Address;

        // Skip if both addresses are null/empty
        if (!hasIPv4 && !hasIPv6) {
          return;
        }

        hasValidServer = true;

        if (server?.Type) {
          infoItems.push({
            label: `DNS Type (#${index + 1})`,
            value: server.Type,
          });
        }
        if (hasIPv4) {
          infoItems.push({
            label: `DNS Server (#${index + 1})`,
            value: server.IPv4Address,
          });
        } else if (hasIPv6) {
          infoItems.push({
            label: `DNS Server (#${index + 1})`,
            value: server.IPv6Address,
          });
        }
      });

      return hasValidServer;
    };

    const hasServers = dns.FromDHCP
      ? addDnsServers(dns.DNSFromDHCP)
      : addDnsServers(dns.DNSManual);

    if (!hasServers) {
      infoItems.push({
        label: "DNS Servers",
        value: "Not Configured",
      });
    }
  }

  useEffect(() => {
    if (dns?.FromDHCP !== undefined) {
      setDNSFromDHCP(dns.FromDHCP);
    }
  }, [dns?.FromDHCP]);

  // Handlers
  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  const handleOpenDialog = () => {
    const fromDhcp = dns?.FromDHCP ?? false;

    // Parse search domains
    const domains: SearchDomainEntry[] =
      dns?.SearchDomain && dns.SearchDomain.length > 0
        ? dns.SearchDomain.map((domain: string) => ({
            id: generateSearchDomainId(),
            domain,
          }))
        : [];

    // Parse DNS servers
    const parseDnsServers = (
      servers?: Array<Record<string, any>>,
    ): DNSServerEntry[] => {
      if (!servers?.length) {
        return [];
      }

      return servers.map((server) => {
        const id = generateDnsServerId();
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
        return { id, type: "" as const, server: "" };
      });
    };

    const serverSource = fromDhcp ? dns?.DNSFromDHCP : dns?.DNSManual;
    const parsedServers = parseDnsServers(serverSource);

    setDNSFromDHCP(fromDhcp);
    setSearchDomains(domains);
    setDnsServers(parsedServers);
    setOriginalValues({
      DNSFromDHCP: fromDhcp,
      searchDomains: [...domains],
      dnsServers: parsedServers.map((s) => ({ ...s })),
    });
    setDialogOpen(true);
  };

  const handleAddSearchDomain = () => {
    setSearchDomains([
      ...searchDomains,
      { id: generateSearchDomainId(), domain: "" },
    ]);
  };

  const handleRemoveSearchDomain = (index: number) => {
    setSearchDomains(searchDomains.filter((_, i) => i !== index));
  };

  const handleSearchDomainChange = (index: number, value: string) => {
    const updated = searchDomains.map((entry, i) =>
      i === index ? { ...entry, domain: value } : entry,
    );
    setSearchDomains(updated);
  };

  const handleAddServer = () => {
    setDnsServers([
      ...dnsServers,
      { id: generateDnsServerId(), type: "", server: "" },
    ]);
  };

  const handleRemoveServer = (index: number) => {
    setDnsServers(dnsServers.filter((_, i) => i !== index));
  };

  const handleServerChange = (
    index: number,
    field: "type" | "server",
    value: string,
  ) => {
    const updated = dnsServers.map((server, i) =>
      i === index ? { ...server, [field]: value } : server,
    );
    setDnsServers(updated);
  };

  // Check if there are any changes
  const hasChanges = useFormChanges(
    { DNSFromDHCP, searchDomains, dnsServers },
    originalValues,
    {
      searchDomains: (
        current: SearchDomainEntry[],
        original: SearchDomainEntry[],
      ) => {
        if (current.length !== original.length) return false;
        return current.every(
          (entry, i) => entry.domain === original[i]?.domain,
        );
      },
      dnsServers: (current: DNSServerEntry[], original: DNSServerEntry[]) => {
        if (current.length !== original.length) return false;
        return current.every(
          (server, i) =>
            server.type === original[i]?.type &&
            server.server === original[i]?.server,
        );
      },
    },
  );

  // Validate servers: if type is set, server must be set and vice versa
  const isServersValid = dnsServers.every((server) => {
    const hasType = !!server.type;
    const hasServer = !!server.server.trim();
    // Both empty or both filled is valid
    return hasType === hasServer;
  });

  const isValid = DNSFromDHCP || isServersValid;

  const handleUpdateDNS = () => {
    // Build the DNS manual configuration array from valid servers
    const validServers = dnsServers.filter((s) => s.type && s.server.trim());
    const dnsManualConfig = validServers.map((s) => {
      const serverConfig: Record<string, any> = { Type: s.type };
      if (s.type === "IPv4") {
        serverConfig.IPv4Address = s.server.trim();
        serverConfig.IPv6Address = null;
      } else if (s.type === "IPv6") {
        serverConfig.IPv4Address = null;
        serverConfig.IPv6Address = s.server.trim();
      }
      return serverConfig;
    });

    // Build search domain list
    const searchDomainConfig = searchDomains
      .filter((entry) => entry.domain.trim())
      .map((entry) => entry.domain.trim());

    setDNSMutation.mutate(
      {
        from_dhcp: DNSFromDHCP,
        search_domain: searchDomainConfig,
        dns_manual: dnsManualConfig,
      },
      {
        onSuccess: () => {
          toast.success("DNS settings updated successfully");
          setDialogOpen(false);
        },
        onError: () => {
          toast.error("Failed to update DNS settings");
        },
      },
    );
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load device DNS settings"}
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

        {/* DNS Table */}
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

        {/* DNS Configuration Dialog */}
        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Configure Domain Name System</DialogTitle>
          <DialogContent>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
            >
              <FormControl fullWidth>
                <InputLabel>DNS From DHCP</InputLabel>
                <Select
                  value={DNSFromDHCP ? "Enabled" : "Disabled"}
                  label="DNS From DHCP"
                  onChange={(e) => setDNSFromDHCP(e.target.value === "Enabled")}
                >
                  <MenuItem value="Enabled">Enabled</MenuItem>
                  <MenuItem value="Disabled">Disabled</MenuItem>
                </Select>
                <FormHelperText>
                  Set whether the device obtains DNS settings from DHCP.
                </FormHelperText>
              </FormControl>

              {/* Search Domains */}
              <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <Typography variant="subtitle2">Search Domains</Typography>
                {searchDomains.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No search domains configured.
                  </Typography>
                ) : (
                  searchDomains.map((entry, index) => (
                    <Box
                      key={entry.id}
                      sx={{ display: "flex", gap: 2, alignItems: "center" }}
                    >
                      <TextField
                        fullWidth
                        label={`Domain #${index + 1}`}
                        value={entry.domain}
                        onChange={(e) =>
                          handleSearchDomainChange(index, e.target.value)
                        }
                        disabled={DNSFromDHCP}
                        placeholder="example.com"
                      />
                      <IconButton
                        onClick={() => handleRemoveSearchDomain(index)}
                        disabled={DNSFromDHCP}
                        color="error"
                      >
                        <TrashCan size={20} />
                      </IconButton>
                    </Box>
                  ))
                )}
                <Button
                  startIcon={<AddAlt size={16} />}
                  onClick={handleAddSearchDomain}
                  variant="outlined"
                  disabled={DNSFromDHCP}
                >
                  Add Domain
                </Button>
              </Box>

              {/* DNS Servers */}
              <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <Typography variant="subtitle2">DNS Servers</Typography>
                {dnsServers.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No DNS servers configured.
                  </Typography>
                ) : (
                  dnsServers.map((serverEntry, index) => (
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
                          onChange={(e) =>
                            handleServerChange(index, "type", e.target.value)
                          }
                          disabled={DNSFromDHCP}
                        >
                          <MenuItem value="IPv4">IPv4</MenuItem>
                          <MenuItem value="IPv6">IPv6</MenuItem>
                        </Select>
                      </FormControl>
                      <TextField
                        fullWidth
                        label={`DNS Server #${index + 1}`}
                        value={serverEntry.server}
                        onChange={(e) =>
                          handleServerChange(index, "server", e.target.value)
                        }
                        disabled={DNSFromDHCP}
                        placeholder={
                          serverEntry.type === "IPv4"
                            ? "8.8.8.8"
                            : serverEntry.type === "IPv6"
                              ? "2001:4860:4860::8888"
                              : "Select type first"
                        }
                      />
                      <IconButton
                        onClick={() => handleRemoveServer(index)}
                        disabled={DNSFromDHCP}
                        color="error"
                      >
                        <TrashCan size={20} />
                      </IconButton>
                    </Box>
                  ))
                )}
                <Button
                  startIcon={<AddAlt size={16} />}
                  onClick={handleAddServer}
                  variant="outlined"
                  disabled={DNSFromDHCP}
                >
                  Add Server
                </Button>
              </Box>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Cancel</Button>
            <Button
              onClick={handleUpdateDNS}
              variant="contained"
              disabled={setDNSMutation.isPending || !hasChanges || !isValid}
            >
              {setDNSMutation.isPending ? (
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
