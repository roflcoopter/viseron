import { UserAvatar } from "@carbon/icons-react";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";

import { ROLE_LABELS } from "lib/api/auth";
import * as types from "lib/types";

export function UserInfo({ user }: { user: types.AuthUserResponse }) {
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
