import { PlayFilledAlt, Save } from "@carbon/icons-react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMemo, useState } from "react";

import { ErrorMessage } from "components/error/ErrorMessage";
import { Loading } from "components/loading/Loading";
import { useTitle } from "hooks/UseTitle";
import {
  useLDAPConfig,
  useSaveLDAPConfig,
  useTestLDAPConfig,
} from "lib/api/ldap";
import * as types from "lib/types";

const EMPTY_CONFIG: types.LDAPConfig = {
  enabled: false,
  url: "",
  bind_dn: "",
  bind_password: "",
  bind_password_set: false,
  user_base_dn: "",
  user_filter: "(sAMAccountName={username})",
  username_attribute: "sAMAccountName",
  name_attribute: "displayName",
  group_base_dn: "",
  group_filter: "(member={user_dn})",
  admin_groups: [],
  write_groups: [],
  read_groups: [],
  default_role: "read",
};

function groupsToText(groups: string[]) {
  return groups.join("\n");
}

function textToGroups(value: string) {
  return value
    .split(/[\n,]/)
    .map((group) => group.trim())
    .filter(Boolean);
}

function LDAPForm({ initialConfig }: { initialConfig: types.LDAPConfig }) {
  const saveLDAPConfig = useSaveLDAPConfig();
  const testLDAPConfig = useTestLDAPConfig();
  const [config, setConfig] = useState<types.LDAPConfig>(initialConfig);
  const [testUsername, setTestUsername] = useState("");
  const [testPassword, setTestPassword] = useState("");
  const [saveResult, setSaveResult] = useState<types.LDAPSaveResponse | null>(
    null,
  );
  const [testResult, setTestResult] = useState<types.LDAPTestResponse | null>(
    null,
  );

  const canSubmit = useMemo(() => {
    if (!config.enabled) {
      return true;
    }
    return Boolean(config.url.trim() && config.user_base_dn.trim());
  }, [config.enabled, config.url, config.user_base_dn]);

  const updateConfig = <K extends keyof types.LDAPConfig>(
    key: K,
    value: types.LDAPConfig[K],
  ) => {
    setConfig((currentConfig) => ({ ...currentConfig, [key]: value }));
  };

  const handleSave = () => {
    saveLDAPConfig.mutate(config, {
      onSuccess: (data) => {
        setSaveResult(data);
      },
    });
  };

  const handleTest = () => {
    testLDAPConfig.mutate(
      { config, username: testUsername, password: testPassword },
      {
        onSuccess: (data) => {
          setTestResult(data);
        },
      },
    );
  };

  return (
    <Container
      maxWidth="lg"
      sx={{ paddingX: { xs: 1, md: 2 }, paddingY: 1 }}
    >
      <Paper sx={{ padding: { xs: 2, md: 3 } }}>
        <Stack spacing={2.5}>
          <Box
            sx={{
              alignItems: "center",
              display: "flex",
              justifyContent: "space-between",
              gap: 2,
            }}
          >
            <Typography variant="h6">LDAP / Active Directory</Typography>
            <FormControlLabel
              control={
                <Switch
                  checked={config.enabled}
                  onChange={(event) =>
                    updateConfig("enabled", event.target.checked)
                  }
                />
              }
              label="Enabled"
            />
          </Box>

          {saveResult?.restart_required && (
            <Alert severity="warning">
              Restart Viseron to apply the webserver authentication change.
            </Alert>
          )}
          {saveResult && !saveResult.success && (
            <Alert severity="error">{saveResult.errors.join(", ")}</Alert>
          )}
          {testResult && (
            <Alert severity="success">
              {testResult.user
                ? `${testResult.user.name} (${testResult.user.username})`
                : "Bind successful"}
            </Alert>
          )}

          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              fullWidth
              required={config.enabled}
              label="LDAP URL"
              value={config.url}
              placeholder="ldaps://dc.example.org"
              onChange={(event) => updateConfig("url", event.target.value)}
            />
            <TextField
              fullWidth
              select
              label="Default role"
              value={config.default_role}
              onChange={(event) =>
                updateConfig(
                  "default_role",
                  event.target.value as types.LDAPRole,
                )
              }
            >
              <MenuItem value="read">Read</MenuItem>
              <MenuItem value="write">Write</MenuItem>
              <MenuItem value="admin">Admin</MenuItem>
            </TextField>
          </Stack>

          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              fullWidth
              label="Bind DN"
              value={config.bind_dn}
              onChange={(event) => updateConfig("bind_dn", event.target.value)}
            />
            <TextField
              fullWidth
              label="Bind password"
              type="password"
              value={config.bind_password}
              placeholder={config.bind_password_set ? "Already saved" : ""}
              onChange={(event) =>
                updateConfig("bind_password", event.target.value)
              }
            />
          </Stack>

          <Divider />

          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              fullWidth
              required={config.enabled}
              label="User base DN"
              value={config.user_base_dn}
              onChange={(event) =>
                updateConfig("user_base_dn", event.target.value)
              }
            />
            <TextField
              fullWidth
              label="User filter"
              value={config.user_filter}
              onChange={(event) =>
                updateConfig("user_filter", event.target.value)
              }
            />
          </Stack>

          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              fullWidth
              label="Username attribute"
              value={config.username_attribute}
              onChange={(event) =>
                updateConfig("username_attribute", event.target.value)
              }
            />
            <TextField
              fullWidth
              label="Name attribute"
              value={config.name_attribute}
              onChange={(event) =>
                updateConfig("name_attribute", event.target.value)
              }
            />
          </Stack>

          <Divider />

          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              fullWidth
              label="Group base DN"
              value={config.group_base_dn}
              onChange={(event) =>
                updateConfig("group_base_dn", event.target.value)
              }
            />
            <TextField
              fullWidth
              label="Group filter"
              value={config.group_filter}
              onChange={(event) =>
                updateConfig("group_filter", event.target.value)
              }
            />
          </Stack>

          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              fullWidth
              multiline
              minRows={3}
              label="Admin groups"
              value={groupsToText(config.admin_groups)}
              onChange={(event) =>
                updateConfig("admin_groups", textToGroups(event.target.value))
              }
            />
            <TextField
              fullWidth
              multiline
              minRows={3}
              label="Write groups"
              value={groupsToText(config.write_groups)}
              onChange={(event) =>
                updateConfig("write_groups", textToGroups(event.target.value))
              }
            />
            <TextField
              fullWidth
              multiline
              minRows={3}
              label="Read groups"
              value={groupsToText(config.read_groups)}
              onChange={(event) =>
                updateConfig("read_groups", textToGroups(event.target.value))
              }
            />
          </Stack>

          <Divider />

          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              fullWidth
              label="Test username"
              value={testUsername}
              onChange={(event) => setTestUsername(event.target.value)}
            />
            <TextField
              fullWidth
              label="Test password"
              type="password"
              value={testPassword}
              onChange={(event) => setTestPassword(event.target.value)}
            />
          </Stack>

          <Box
            sx={{
              display: "flex",
              gap: 1,
              justifyContent: "flex-end",
              flexWrap: "wrap",
            }}
          >
            <Button
              variant="outlined"
              startIcon={<PlayFilledAlt />}
              disabled={
                !config.enabled || !canSubmit || testLDAPConfig.isPending
              }
              onClick={handleTest}
            >
              Test
            </Button>
            <Button
              variant="contained"
              startIcon={<Save />}
              disabled={!canSubmit || saveLDAPConfig.isPending}
              onClick={handleSave}
            >
              Save
            </Button>
          </Box>
        </Stack>
      </Paper>
    </Container>
  );
}

function LDAP() {
  useTitle("LDAP");
  const ldapConfig = useLDAPConfig();

  if (ldapConfig.isLoading) {
    return <Loading text="Loading LDAP settings" />;
  }

  if (ldapConfig.isError || !ldapConfig.data) {
    return (
      <ErrorMessage
        text="Error loading LDAP settings"
        subtext={ldapConfig.error?.message}
      />
    );
  }

  return (
    <LDAPForm initialConfig={{ ...EMPTY_CONFIG, ...ldapConfig.data.config }} />
  );
}

export default LDAP;
