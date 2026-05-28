import { Add, Save, TrashCan } from "@carbon/icons-react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Container from "@mui/material/Container";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import ListItemText from "@mui/material/ListItemText";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Select, { SelectChangeEvent } from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useMemo, useState } from "react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import { useTitle } from "hooks/UseTitle";
import {
  useCameraAccessConfig,
  useSaveCameraAccessConfig,
} from "lib/api/cameraAccess";
import { useCamerasAll } from "lib/api/cameras";
import * as types from "lib/types";

const EMPTY_CONFIG: types.CameraAccessConfig = {
  camera_groups: [],
  ldap_camera_access: [],
};

const SELECT_ALL_CAMERAS = "<select-all-cameras>";

type CameraOption = {
  id: string;
  name: string;
  failed: boolean;
};

function selectedValues(value: string | string[]) {
  return typeof value === "string" ? value.split(",") : value;
}

function groupsToText(groups: string[]) {
  return groups.join("\n");
}

function textToGroups(value: string) {
  return value
    .split("\n")
    .map((group) => group.trim())
    .filter(Boolean);
}

function nextGroupId(groups: types.CameraAccessGroup[]) {
  const existingIds = new Set(groups.map((group) => group.id));
  let index = groups.length + 1;
  let groupId = `camera_group_${index}`;
  while (existingIds.has(groupId)) {
    index += 1;
    groupId = `camera_group_${index}`;
  }
  return groupId;
}

function ruleKey() {
  return `rule_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function CameraMultiSelect({
  label,
  value,
  cameras,
  onChange,
}: {
  label: string;
  value: string[];
  cameras: CameraOption[];
  onChange: (cameraIds: string[]) => void;
}) {
  const handleChange = (event: SelectChangeEvent<string[]>) => {
    const nextValue = selectedValues(event.target.value);
    if (nextValue.includes(SELECT_ALL_CAMERAS)) {
      onChange(
        value.length === cameras.length
          ? []
          : cameras.map((camera) => camera.id),
      );
      return;
    }
    onChange(nextValue);
  };

  return (
    <FormControl fullWidth>
      <InputLabel>{label}</InputLabel>
      <Select
        multiple
        label={label}
        value={value}
        onChange={handleChange}
        renderValue={(selected) =>
          (selected as string[])
            .map((cameraId) => cameras.find((camera) => camera.id === cameraId))
            .map((camera) => camera?.name || "")
            .filter(Boolean)
            .join(", ")
        }
      >
        <MenuItem value={SELECT_ALL_CAMERAS}>
          <Checkbox
            checked={value.length === cameras.length && cameras.length > 0}
          />
          <ListItemText primary="All cameras" />
        </MenuItem>
        {cameras.map((camera) => (
          <MenuItem key={camera.id} value={camera.id}>
            <Checkbox checked={value.includes(camera.id)} />
            <ListItemText
              primary={camera.name}
              secondary={camera.failed ? "Failed" : undefined}
            />
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}

function CameraGroupMultiSelect({
  label,
  value,
  groups,
  onChange,
}: {
  label: string;
  value: string[];
  groups: types.CameraAccessGroup[];
  onChange: (groupIds: string[]) => void;
}) {
  return (
    <FormControl fullWidth>
      <InputLabel>{label}</InputLabel>
      <Select
        multiple
        label={label}
        value={value}
        onChange={(event) => onChange(selectedValues(event.target.value))}
        renderValue={(selected) =>
          (selected as string[])
            .map((groupId) => groups.find((group) => group.id === groupId))
            .map((group) => group?.name || "")
            .filter(Boolean)
            .join(", ")
        }
      >
        {groups.map((group) => (
          <MenuItem key={group.id} value={group.id}>
            <Checkbox checked={value.includes(group.id)} />
            <ListItemText primary={group.name} secondary={group.id} />
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}

function CameraAccessForm({
  initialConfig,
}: {
  initialConfig: types.CameraAccessConfig;
}) {
  const saveCameraAccessConfig = useSaveCameraAccessConfig();
  const camerasAll = useCamerasAll();
  const [config, setConfig] = useState<types.CameraAccessConfig>(initialConfig);
  const [ruleKeys, setRuleKeys] = useState(() =>
    initialConfig.ldap_camera_access.map(() => ruleKey()),
  );
  const [saveResult, setSaveResult] =
    useState<types.CameraAccessSaveResponse | null>(null);

  const cameraOptions = useMemo<CameraOption[]>(
    () =>
      Object.values(camerasAll.combinedData)
        .map((camera) => ({
          id: camera.identifier,
          name: camera.name || camera.identifier,
          failed: camera.failed,
        }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [camerasAll.combinedData],
  );

  const updateGroup = (
    index: number,
    update: Partial<types.CameraAccessGroup>,
  ) => {
    setConfig((currentConfig) => {
      const oldId = currentConfig.camera_groups[index].id;
      const nextGroups = currentConfig.camera_groups.map((group, groupIndex) =>
        groupIndex === index ? { ...group, ...update } : group,
      );
      const newId = nextGroups[index].id;
      const nextRules =
        oldId === newId
          ? currentConfig.ldap_camera_access
          : currentConfig.ldap_camera_access.map((rule) => ({
              ...rule,
              camera_groups: rule.camera_groups.map((groupId) =>
                groupId === oldId ? newId : groupId,
              ),
            }));
      return {
        ...currentConfig,
        camera_groups: nextGroups,
        ldap_camera_access: nextRules,
      };
    });
  };

  const addGroup = () => {
    setConfig((currentConfig) => ({
      ...currentConfig,
      camera_groups: [
        ...currentConfig.camera_groups,
        {
          id: nextGroupId(currentConfig.camera_groups),
          name: "Camera group",
          cameras: [],
        },
      ],
    }));
  };

  const removeGroup = (index: number) => {
    setConfig((currentConfig) => {
      const groupId = currentConfig.camera_groups[index].id;
      return {
        ...currentConfig,
        camera_groups: currentConfig.camera_groups.filter(
          (_group, groupIndex) => groupIndex !== index,
        ),
        ldap_camera_access: currentConfig.ldap_camera_access.map((rule) => ({
          ...rule,
          camera_groups: rule.camera_groups.filter((id) => id !== groupId),
        })),
      };
    });
  };

  const updateRule = (
    index: number,
    update: Partial<types.LDAPCameraAccessRule>,
  ) => {
    setConfig((currentConfig) => ({
      ...currentConfig,
      ldap_camera_access: currentConfig.ldap_camera_access.map(
        (rule, ruleIndex) =>
          ruleIndex === index ? { ...rule, ...update } : rule,
      ),
    }));
  };

  const addRule = () => {
    setRuleKeys((currentRuleKeys) => [...currentRuleKeys, ruleKey()]);
    setConfig((currentConfig) => ({
      ...currentConfig,
      ldap_camera_access: [
        ...currentConfig.ldap_camera_access,
        { groups: [], camera_groups: [], cameras: [] },
      ],
    }));
  };

  const removeRule = (index: number) => {
    setRuleKeys((currentRuleKeys) =>
      currentRuleKeys.filter((_ruleKey, ruleIndex) => ruleIndex !== index),
    );
    setConfig((currentConfig) => ({
      ...currentConfig,
      ldap_camera_access: currentConfig.ldap_camera_access.filter(
        (_rule, ruleIndex) => ruleIndex !== index,
      ),
    }));
  };

  const handleSave = () => {
    saveCameraAccessConfig.mutate(config, {
      onSuccess: (data) => {
        setSaveResult(data);
      },
    });
  };

  return (
    <Container maxWidth="lg" sx={{ paddingX: { xs: 1, md: 2 }, paddingY: 1 }}>
      <Paper sx={{ padding: { xs: 2, md: 3 } }}>
        <Stack spacing={2.5}>
          <Box
            sx={{
              alignItems: "center",
              display: "flex",
              gap: 2,
              justifyContent: "space-between",
            }}
          >
            <Typography variant="h6">Camera Access</Typography>
            <Button
              variant="contained"
              startIcon={<Save />}
              disabled={saveCameraAccessConfig.isPending}
              onClick={handleSave}
            >
              Save
            </Button>
          </Box>

          {saveResult?.restart_required && (
            <Alert severity="warning">
              Restart Viseron to apply all camera access changes.
            </Alert>
          )}
          {saveResult && !saveResult.success && (
            <Alert severity="error">{saveResult.errors.join(", ")}</Alert>
          )}

          <Stack direction="row" justifyContent="space-between" spacing={2}>
            <Typography variant="subtitle1">Camera groups</Typography>
            <Button variant="outlined" startIcon={<Add />} onClick={addGroup}>
              Add group
            </Button>
          </Stack>
          <Stack spacing={2}>
            {config.camera_groups.map((group, index) => (
              <Paper key={group.id} variant="outlined" sx={{ padding: 2 }}>
                <Stack spacing={2}>
                  <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                    <TextField
                      fullWidth
                      required
                      label="ID"
                      value={group.id}
                      onChange={(event) =>
                        updateGroup(index, { id: event.target.value.trim() })
                      }
                    />
                    <TextField
                      fullWidth
                      label="Name"
                      value={group.name}
                      onChange={(event) =>
                        updateGroup(index, { name: event.target.value })
                      }
                    />
                    <Tooltip title="Delete group">
                      <span>
                        <IconButton
                          color="error"
                          onClick={() => removeGroup(index)}
                          sx={{ height: 56, width: 56 }}
                        >
                          <TrashCan />
                        </IconButton>
                      </span>
                    </Tooltip>
                  </Stack>
                  <CameraMultiSelect
                    label="Cameras"
                    cameras={cameraOptions}
                    value={group.cameras}
                    onChange={(cameras) => updateGroup(index, { cameras })}
                  />
                </Stack>
              </Paper>
            ))}
          </Stack>

          <Divider />

          <Stack direction="row" justifyContent="space-between" spacing={2}>
            <Typography variant="subtitle1">LDAP camera access</Typography>
            <Button variant="outlined" startIcon={<Add />} onClick={addRule}>
              Add rule
            </Button>
          </Stack>
          <Stack spacing={2}>
            {config.ldap_camera_access.map((rule, index) => (
              <Paper
                key={ruleKeys[index]}
                variant="outlined"
                sx={{ padding: 2 }}
              >
                <Stack spacing={2}>
                  <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                    <TextField
                      fullWidth
                      multiline
                      minRows={3}
                      label="AD groups"
                      value={groupsToText(rule.groups)}
                      onChange={(event) =>
                        updateRule(index, {
                          groups: textToGroups(event.target.value),
                        })
                      }
                    />
                    <Tooltip title="Delete rule">
                      <span>
                        <IconButton
                          color="error"
                          onClick={() => removeRule(index)}
                          sx={{ height: 56, width: 56 }}
                        >
                          <TrashCan />
                        </IconButton>
                      </span>
                    </Tooltip>
                  </Stack>
                  <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                    <CameraGroupMultiSelect
                      label="Camera groups"
                      groups={config.camera_groups}
                      value={rule.camera_groups}
                      onChange={(cameraGroups) =>
                        updateRule(index, { camera_groups: cameraGroups })
                      }
                    />
                    <CameraMultiSelect
                      label="Direct cameras"
                      cameras={cameraOptions}
                      value={rule.cameras}
                      onChange={(cameras) => updateRule(index, { cameras })}
                    />
                  </Stack>
                </Stack>
              </Paper>
            ))}
          </Stack>
        </Stack>
      </Paper>
    </Container>
  );
}

function CameraAccess() {
  useTitle("Camera Access");
  const cameraAccessConfig = useCameraAccessConfig();

  if (cameraAccessConfig.isLoading) {
    return <Loading text="Loading camera access" />;
  }

  if (cameraAccessConfig.isError || !cameraAccessConfig.data) {
    return (
      <ErrorMessage
        text="Error loading camera access"
        subtext={cameraAccessConfig.error?.message}
      />
    );
  }

  return (
    <CameraAccessForm
      initialConfig={{ ...EMPTY_CONFIG, ...cameraAccessConfig.data.config }}
    />
  );
}

export default CameraAccess;
