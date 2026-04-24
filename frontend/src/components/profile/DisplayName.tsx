import { Save } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useState } from "react";

import { useProfileUpdateDisplayName } from "lib/api/profile";
import * as types from "lib/types";

export function DisplayName({ user }: { user: types.AuthUserResponse }) {
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
