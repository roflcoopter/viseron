import { Help, Vlan } from "@carbon/icons-react";
import {
  Box,
  Button,
  Chip,
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
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useState } from "react";

import { useToast } from "hooks/UseToast";
import { useFormChanges } from "hooks/useFormChanges";
import {
  useGetDeviceNetworkProtocols,
  useSetDeviceNetworkProtocols,
} from "lib/api/actions/onvif/device";

import { QueryWrapper } from "../../config/QueryWrapper";

interface DeviceNetworkProtocolsProps {
  cameraIdentifier: string;
  deviceCapabilities?: any;
}

export function DeviceNetworkProtocols({
  cameraIdentifier,
  deviceCapabilities,
}: DeviceNetworkProtocolsProps) {
  // Check if network configuration is not supported
  const isNetworkConfigNotSupported =
    deviceCapabilities?.System?.NetworkConfigNotSupported === true;

  const TITLE = "Network Protocols";
  const DESC =
    "Manage network protocols for this device. The port on each protocol must be unique. Some cameras will 'perform' or 'require' a reboot after this configuration is changed.";

  const toast = useToast();

  // ONVIF API hooks
  const { data, isLoading, isError, error } = useGetDeviceNetworkProtocols(
    cameraIdentifier,
    !isNetworkConfigNotSupported,
  );
  const setProtocolsMutation = useSetDeviceNetworkProtocols(cameraIdentifier);

  const protocols = data?.network_protocols;

  // Section state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProtocol, setEditingProtocol] = useState<{
    Name: string;
    Enabled: boolean;
    Port: number[];
  } | null>(null);
  const [protocolEnabled, setProtocolEnabled] = useState(false);
  const [protocolPorts, setProtocolPorts] = useState("");

  // Store original values to detect changes
  const [originalValues, setOriginalValues] = useState<{
    enabled: boolean;
    ports: string;
  }>({
    enabled: false,
    ports: "",
  });

  // Handlers
  const handleEditProtocol = (protocol: {
    Name: string;
    Enabled: boolean;
    Port: number[];
  }) => {
    setEditingProtocol(protocol);
    setProtocolEnabled(protocol.Enabled);
    const portString = protocol.Port[0]?.toString() || "";
    setProtocolPorts(portString);
    setOriginalValues({
      enabled: protocol.Enabled,
      ports: portString,
    });
    setDialogOpen(true);
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  // Check if there are any changes using useFormChanges hook
  const currentValues = {
    enabled: protocolEnabled,
    ports: protocolPorts,
  };

  const hasChanges = useFormChanges(currentValues, originalValues);

  const handleUpdateProtocol = () => {
    if (!editingProtocol || !protocols) return;

    // Parse port as single number
    const port = parseInt(protocolPorts.trim(), 10);

    if (isNaN(port) || port <= 0 || port > 65535) {
      toast.error("Please enter a valid port number (1-65535)");
      return;
    }

    // Build updated protocols array
    const updatedProtocols = protocols.map(
      (p: { Name: string; Enabled: boolean; Port: number[] }) => {
        if (p.Name === editingProtocol.Name) {
          return {
            Name: p.Name,
            Enabled: protocolEnabled,
            Port: [port], // Wrap single port in array
          };
        }
        return p;
      },
    );

    setProtocolsMutation.mutate(
      { network_protocols: updatedProtocols },
      {
        onSuccess: () => {
          toast.success(
            `Protocol "${editingProtocol.Name}" updated successfully`,
          );
          handleDialogClose();
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to update protocol");
        },
      },
    );
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load device network protocols"}
      isEmpty={!protocols || protocols.length === 0}
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
        </Box>

        {/* Protocols List */}
        <Stack direction="row" flexWrap="wrap" gap={0.5}>
          {protocols?.map(
            (protocol: { Name: string; Enabled: boolean; Port: number[] }) => (
              <Tooltip
                key={protocol.Name}
                title={`Port: ${protocol.Port.join(", ")}`}
                placement="top"
                arrow
              >
                <Chip
                  sx={{
                    pl: 0.5,
                  }}
                  label={protocol.Name}
                  size="medium"
                  icon={<Vlan size={16} />}
                  color={protocol.Enabled ? "success" : "error"}
                  variant={protocol.Enabled ? "filled" : "outlined"}
                  onClick={() => handleEditProtocol(protocol)}
                />
              </Tooltip>
            ),
          )}
        </Stack>

        {/* Configure Protocol Dialog */}
        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>
            {editingProtocol
              ? `Configure ${editingProtocol.Name} Protocol`
              : "Configure Network Protocols"}
          </DialogTitle>
          <DialogContent>
            {editingProtocol ? (
              <Box
                sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}
              >
                <FormControl fullWidth>
                  <InputLabel>Status</InputLabel>
                  <Select
                    value={protocolEnabled ? "Enabled" : "Disabled"}
                    label="Status"
                    onChange={(e) =>
                      setProtocolEnabled(e.target.value === "Enabled")
                    }
                  >
                    <MenuItem value="Enabled">Enabled</MenuItem>
                    <MenuItem value="Disabled">Disabled</MenuItem>
                  </Select>
                  <FormHelperText>
                    Enable or disable this network protocol.
                  </FormHelperText>
                </FormControl>
                <TextField
                  fullWidth
                  type="number"
                  label="Port"
                  value={protocolPorts}
                  onChange={(e) => setProtocolPorts(e.target.value)}
                  placeholder="e.g., 80"
                  helperText="Enter port number (1-65535)."
                  slotProps={{
                    htmlInput: {
                      min: 1,
                      max: 65535,
                    },
                  }}
                />
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
                Click on a protocol chip above to configure it.
              </Typography>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>
              {editingProtocol ? "Cancel" : "Close"}
            </Button>
            {editingProtocol && (
              <Button
                onClick={handleUpdateProtocol}
                variant="contained"
                disabled={
                  !hasChanges ||
                  !protocolPorts.trim() ||
                  setProtocolsMutation.isPending
                }
              >
                {setProtocolsMutation.isPending ? (
                  <CircularProgress enableTrackSlot size={24} />
                ) : (
                  "Save"
                )}
              </Button>
            )}
          </DialogActions>
        </Dialog>
      </Box>
    </QueryWrapper>
  );
}
