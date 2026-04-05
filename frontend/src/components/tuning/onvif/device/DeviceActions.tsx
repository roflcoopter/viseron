import { Help, Industry, Power, Renew } from "@carbon/icons-react";
import {
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import { useState } from "react";

import { useToast } from "hooks/UseToast";
import {
  useDeviceFactoryReset,
  useDeviceReboot,
} from "lib/api/actions/onvif/device";

interface DeviceActionsProps {
  cameraIdentifier: string;
  isLoading?: boolean;
  isAvailable?: boolean;
}

export function DeviceActions({
  cameraIdentifier,
  isLoading,
  isAvailable,
}: DeviceActionsProps) {
  const TITLE = "Actions";
  const DESC =
    "Perform actions on the ONVIF device. Some cameras may ignore the actions defined here.";
  const toast = useToast();

  const [rebootOpen, setRebootOpen] = useState(false);
  const [factoryResetOpen, setFactoryResetOpen] = useState(false);

  // ONVIF API hooks
  const rebootMutation = useDeviceReboot(cameraIdentifier);
  const factoryResetMutation = useDeviceFactoryReset(cameraIdentifier);

  // Handlers
  const handleReboot = () => {
    rebootMutation.mutate(undefined, {
      onSuccess: () => {
        setRebootOpen(false);
        toast.success("Reboot command sent successfully");
      },
      onError: (err) => {
        toast.error(err?.message || "Failed to reboot device");
      },
    });
  };

  const handleFactoryReset = (level: string) => {
    factoryResetMutation.mutate(level, {
      onSuccess: () => {
        setFactoryResetOpen(false);
        toast.success("Factory reset command sent successfully");
      },
      onError: (err) => {
        toast.error(err?.message || "Failed to factory reset device");
      },
    });
  };

  return (
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
      <Box display="flex" flexDirection="column" gap={1}>
        <Button
          variant="contained"
          color="warning"
          fullWidth
          startIcon={
            rebootMutation.isPending || rebootMutation.isSuccess ? (
              <CircularProgress enableTrackSlot size={16} />
            ) : (
              <Power size={16} />
            )
          }
          onClick={() => setRebootOpen(true)}
          disabled={
            rebootMutation.isPending ||
            rebootMutation.isSuccess ||
            !isAvailable ||
            isLoading
          }
        >
          {rebootMutation.isSuccess ? "Rebooting..." : "Reboot Device"}
        </Button>

        <Button
          variant="contained"
          color="warning"
          fullWidth
          startIcon={
            factoryResetMutation.isPending || factoryResetMutation.isSuccess ? (
              <CircularProgress enableTrackSlot size={16} />
            ) : (
              <Industry size={16} />
            )
          }
          onClick={() => setFactoryResetOpen(true)}
          disabled={
            factoryResetMutation.isPending ||
            factoryResetMutation.isSuccess ||
            !isAvailable ||
            isLoading
          }
        >
          {factoryResetMutation.isSuccess
            ? "Factory Resetting..."
            : "Factory Reset Device"}
        </Button>
      </Box>
      <Dialog open={rebootOpen} onClose={() => setRebootOpen(false)}>
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Renew size={24} />
            <Typography variant="h6">Confirm Reboot</Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to reboot this device? The camera will be
            temporarily unavailable during the reboot process.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRebootOpen(false)}>Cancel</Button>
          <Button
            onClick={handleReboot}
            color="warning"
            variant="contained"
            disabled={rebootMutation.isPending}
          >
            {rebootMutation.isPending ? (
              <CircularProgress enableTrackSlot size={20} />
            ) : (
              "Reboot"
            )}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={factoryResetOpen}
        onClose={() => setFactoryResetOpen(false)}
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Renew size={24} />
            <Typography variant="h6">Confirm Factory Reset</Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to perform a factory reset on this device?
            Sometimes the camera connection will be lost and it will revert to
            factory settings. You need to set it back up afterwards. This action
            cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFactoryResetOpen(false)}>Cancel</Button>
          <Button
            onClick={() => handleFactoryReset("Soft")}
            color="warning"
            variant="contained"
            disabled={factoryResetMutation.isPending}
          >
            {factoryResetMutation.isPending ? (
              <CircularProgress enableTrackSlot size={24} />
            ) : (
              "Soft Reset"
            )}
          </Button>
          <Button
            onClick={() => handleFactoryReset("Hard")}
            color="error"
            variant="contained"
            disabled={factoryResetMutation.isPending}
          >
            {factoryResetMutation.isPending ? (
              <CircularProgress enableTrackSlot size={24} />
            ) : (
              "Hard Reset"
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
