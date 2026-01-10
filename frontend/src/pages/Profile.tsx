import { Save, UserAvatar } from "@carbon/icons-react";
import Autocomplete from "@mui/material/Autocomplete";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Container from "@mui/material/Container";
import Divider from "@mui/material/Divider";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuthContext } from "context/AuthContext";
import { useTitle } from "hooks/UseTitle";
import { ROLE_LABELS } from "lib/api/auth";
import {
  useProfileAvailableTimezones,
  useProfileUpdateDisplayName,
  useProfileUpdatePreferences,
} from "lib/api/profile";
import * as types from "lib/types";

function UserInfo({ user }: { user: types.AuthUserResponse }) {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        marginBottom: 3,
      }}
    >
      <Avatar
        sx={{
          width: 64,
          height: 64,
          bgcolor: "primary.main",
          marginRight: 2,
        }}
      >
        <UserAvatar size={32} />
      </Avatar>
      <Box>
        <Typography variant="h5">{user.name}</Typography>
        <Typography variant="body2" color="text.secondary">
          @{user.username}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {ROLE_LABELS[user.role] || user.role}
        </Typography>
      </Box>
    </Box>
  );
}

function DisplayName({ user }: { user: types.AuthUserResponse }) {
  const profileUpdateDisplayName = useProfileUpdateDisplayName();
  const [displayName, setDisplayName] = useState(user?.name ?? "");
  const trimmedDisplayName = displayName.trim();
  const displayNameChanged = trimmedDisplayName !== (user?.name ?? "");
  const handleSaveDisplayName = () => {
    if (!trimmedDisplayName) {
      return;
    }
    profileUpdateDisplayName.mutate({ name: trimmedDisplayName });
  };

  return (
    <Box sx={{ marginBottom: 3 }}>
      <Typography variant="subtitle2" sx={{ marginBottom: 1 }}>
        Display name
      </Typography>
      <TextField
        fullWidth
        value={displayName}
        onChange={(event) => setDisplayName(event.target.value)}
        placeholder="Enter your display name"
        helperText="Does not change your username."
        sx={{ marginBottom: 1.5 }}
      />
      <Box>
        <Button
          variant="contained"
          onClick={handleSaveDisplayName}
          disabled={!displayNameChanged || !trimmedDisplayName}
          loading={profileUpdateDisplayName.isPending}
          loadingPosition="start"
          startIcon={<Save />}
        >
          Save
        </Button>
      </Box>
    </Box>
  );
}

function Preferences({ user }: { user: types.AuthUserResponse }) {
  // Timezone
  const profileAvailableTimezonesQuery = useProfileAvailableTimezones();
  const savedTimezone = user.preferences?.timezone ?? null;
  const [selectedTimezone, setSelectedTimezone] = useState<string | null>(
    savedTimezone,
  );
  const detectedTimezone = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone,
    [],
  );

  // Preferences
  const profileUpdatePreferences = useProfileUpdatePreferences();
  const preferencesHasChanges = selectedTimezone !== savedTimezone;
  const handleSavePreferences = () => {
    profileUpdatePreferences.mutate({ timezone: selectedTimezone });
  };
  return (
    <Box sx={{ marginBottom: 3 }}>
      <Typography variant="subtitle2" sx={{ marginBottom: 1 }}>
        Timezone
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ marginBottom: 2 }}
      >
        Set your preferred timezone for displaying dates and times.
      </Typography>

      <Autocomplete
        value={selectedTimezone}
        onChange={(_event, newValue) => {
          setSelectedTimezone(newValue);
        }}
        options={profileAvailableTimezonesQuery.data?.timezones ?? []}
        loading={profileAvailableTimezonesQuery.isLoading}
        renderInput={(params) => (
          <TextField
            {...params}
            label="Timezone"
            placeholder="Select a timezone..."
            helperText={
              selectedTimezone
                ? " "
                : `Currently using your browser's auto-detected timezone: ${detectedTimezone}`
            }
          />
        )}
        isOptionEqualToValue={(option, value) => option === value}
        clearOnEscape
        autoHighlight
        sx={{ marginBottom: 2 }}
      />

      <Box sx={{ display: "flex", gap: 1 }}>
        <Button
          variant="contained"
          onClick={handleSavePreferences}
          disabled={!preferencesHasChanges}
          loading={profileUpdatePreferences.isPending}
          loadingPosition="start"
          startIcon={<Save />}
        >
          Save
        </Button>
      </Box>
    </Box>
  );
}

function ProfileCard({ user }: { user: types.AuthUserResponse }) {
  return (
    <Card sx={{ maxWidth: 600, width: "100%" }}>
      <CardContent>
        <UserInfo user={user} />
        <DisplayName user={user} />
        <Divider sx={{ marginY: 3 }} />

        <Typography variant="h6" sx={{ marginBottom: 2 }}>
          Preferences
        </Typography>
        <Preferences user={user} />
      </CardContent>
    </Card>
  );
}

function Profile() {
  useTitle("Profile");
  const navigate = useNavigate();
  const { auth, user } = useAuthContext();

  if (!auth.enabled || user === null) {
    navigate("/");
    return null;
  }

  return (
    <Container
      maxWidth={false}
      sx={{
        paddingX: 2,
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start",
      }}
    >
      <ProfileCard user={user} />
    </Container>
  );
}

export default Profile;
