import { AddAlt, Help } from "@carbon/icons-react";
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useState } from "react";

import { useToast } from "hooks/UseToast";
import {
  useAddDeviceScopes,
  useGetDeviceScopes,
  useRemoveDeviceScopes,
  useSetDeviceScopes,
} from "lib/api/actions/onvif/device";

import { QueryWrapper } from "../../config/QueryWrapper";

const prefix = "onvif://www.onvif.org/";

interface DeviceScopesProps {
  cameraIdentifier: string;
  deviceCapabilities?: any;
}

export function DeviceScopes({
  cameraIdentifier,
  deviceCapabilities,
}: DeviceScopesProps) {
  // Check if discovery is not supported
  const isDiscoveryNotSupported =
    deviceCapabilities?.System?.DiscoveryNotSupported === true;

  const TITLE = "Discovery Scopes";
  const DESC =
    "Manage ONVIF discovery scopes, which are used for device discovery in WS-Discovery.";

  const toast = useToast();

  // ONVIF API hooks
  const { data, isLoading, isError, error } = useGetDeviceScopes(
    cameraIdentifier,
    !isDiscoveryNotSupported,
  );
  const addScopesMutation = useAddDeviceScopes(cameraIdentifier);
  const removeScopesMutation = useRemoveDeviceScopes(cameraIdentifier);
  const setScopesMutation = useSetDeviceScopes(cameraIdentifier);

  const scopes = data?.scopes;

  // Section state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<"add" | "edit">("add");
  const [newScope, setNewScope] = useState("");
  const [editingScope, setEditingScope] = useState<string | null>(null);

  // Helper to extract readable name from scope item
  const getScopeName = (scopeItem: string): string => {
    const name = scopeItem.startsWith(prefix)
      ? scopeItem.slice(prefix.length)
      : scopeItem;
    return decodeURI(name);
  };

  // Handlers
  const handleAddScope = () => {
    setDialogMode("add");
    setDialogOpen(true);
  };

  const handleEditScope = (scopeItem: string) => {
    setDialogMode("edit");
    setNewScope(getScopeName(scopeItem));
    setEditingScope(scopeItem);
    setDialogOpen(true);
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
    setNewScope("");
  };

  const handleCreateScope = () => {
    if (newScope) {
      addScopesMutation.mutate([`${prefix}${encodeURI(newScope)}`], {
        onSuccess: () => {
          toast.success(`Scope "${newScope}" created successfully`);
          handleDialogClose();
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to create scope");
        },
      });
    }
  };

  const handleUpdateScope = () => {
    if (newScope && editingScope && scopes) {
      // Get all non-Fixed scopes as array of ScopeItem strings
      const configurableScopes = scopes
        .filter((scope) => scope.ScopeDef !== "Fixed")
        .map((scope) => {
          // Replace the edited scope with new value
          if (scope.ScopeItem === editingScope) {
            return `${prefix}${encodeURI(newScope)}`;
          }
          return scope.ScopeItem;
        });

      setScopesMutation.mutate(configurableScopes, {
        onSuccess: () => {
          toast.success("Scope updated successfully");
          handleDialogClose();
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to update scope");
        },
      });
    }
  };

  const handleDeleteScope = () => {
    if (editingScope) {
      removeScopesMutation.mutate(encodeURI(editingScope), {
        onSuccess: () => {
          toast.success("Scope deleted successfully");
          handleDialogClose();
        },
        onError: (err) => {
          toast.error(err?.message || "Failed to delete scope");
        },
      });
    }
  };

  return (
    <QueryWrapper
      isLoading={isLoading}
      isError={isError}
      errorMessage={error?.message || "Failed to load device scopes"}
      isWarning={isDiscoveryNotSupported}
      warningMessage="Device discovery is not supported by this device"
      isEmpty={!scopes || scopes.length === 0}
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
            startIcon={<AddAlt size={16} />}
            onClick={handleAddScope}
            disabled={isDiscoveryNotSupported}
          >
            Add
          </Button>
        </Box>

        {/* Scopes List */}
        <Stack direction="row" flexWrap="wrap" gap={0.7}>
          {scopes?.map((scope) => (
            <Tooltip
              key={scope.ScopeItem}
              title={scope.ScopeItem}
              placement="top"
              arrow
            >
              <Chip
                label={getScopeName(scope.ScopeItem)}
                size="small"
                variant="filled"
                color={scope.ScopeDef === "Fixed" ? "default" : "primary"}
                onClick={
                  scope.ScopeDef !== "Fixed"
                    ? () => handleEditScope(scope.ScopeItem)
                    : undefined
                }
                sx={{
                  cursor: scope.ScopeDef !== "Fixed" ? "pointer" : "default",
                }}
              />
            </Tooltip>
          ))}
        </Stack>

        {/* Add/Edit Scope Dialog */}
        <Dialog
          open={dialogOpen}
          onClose={handleDialogClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>
            {dialogMode === "add" ? "Add Scope" : "Edit Scope"}
          </DialogTitle>
          <DialogContent>
            <TextField
              autoFocus
              margin="dense"
              label="Scope"
              fullWidth
              variant="outlined"
              value={newScope}
              onChange={(e) => setNewScope(e.target.value)}
              placeholder="e.g., location/office room 1"
              helperText="Spaces and special characters will be automatically encoded"
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Cancel</Button>
            {dialogMode === "add" && (
              <Button
                onClick={handleCreateScope}
                variant="contained"
                disabled={!newScope || addScopesMutation.isPending}
              >
                {addScopesMutation.isPending ? (
                  <CircularProgress enableTrackSlot size={24} />
                ) : (
                  "Add"
                )}
              </Button>
            )}
            {dialogMode === "edit" && (
              <>
                <Button
                  onClick={handleDeleteScope}
                  color="error"
                  disabled={
                    removeScopesMutation.isPending ||
                    setScopesMutation.isPending
                  }
                >
                  {removeScopesMutation.isPending ? (
                    <CircularProgress enableTrackSlot size={24} />
                  ) : (
                    "Delete"
                  )}
                </Button>
                <Button
                  onClick={handleUpdateScope}
                  variant="contained"
                  disabled={
                    !newScope ||
                    setScopesMutation.isPending ||
                    removeScopesMutation.isPending
                  }
                >
                  {setScopesMutation.isPending ? (
                    <CircularProgress enableTrackSlot size={24} />
                  ) : (
                    "Save"
                  )}
                </Button>
              </>
            )}
          </DialogActions>
        </Dialog>
      </Box>
    </QueryWrapper>
  );
}
