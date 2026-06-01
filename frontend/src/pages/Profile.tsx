import { useMediaQuery } from "@mui/material";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Container from "@mui/material/Container";
import Divider from "@mui/material/Divider";
import Typography from "@mui/material/Typography";
import { Theme } from "@mui/material/styles";
import { useNavigate } from "react-router-dom";

import { AccessTokens } from "components/profile/AccessTokens";
import { DisplayName } from "components/profile/DisplayName";
import { Preferences } from "components/profile/Preferences";
import { RevokeAll } from "components/profile/RevokeAll";
import { UserInfo } from "components/profile/UserInfo";
import { useAuthContext } from "context/AuthContext";
import { useTitle } from "hooks/UseTitle";
import * as types from "lib/types";

function ProfileCard({ user }: { user: types.AuthUserResponse }) {
  const small = useMediaQuery((theme: Theme) => theme.breakpoints.down("sm"));

  return (
    <Card
      sx={{
        // Full width on mobile, fixed max width on larger screens
        width: small ? "100%" : "80dvw",
        maxWidth: small ? "100%" : 800,
        paddingX: { xs: 1, md: 2 },
        paddingY: { xs: 0.5, md: 1 },
      }}
    >
      <CardContent>
        <UserInfo user={user} />
        <DisplayName user={user} />
        <Divider sx={{ marginY: 3 }} />

        <Typography variant="h6" sx={{ marginBottom: 2 }}>
          Preferences
        </Typography>
        <Preferences user={user} />

        <Divider sx={{ marginY: 3 }} />
        <Typography variant="h6" sx={{ marginBottom: 2 }}>
          Personal access tokens
        </Typography>
        <AccessTokens />

        <Divider sx={{ marginY: 3 }} />
        <RevokeAll />
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
        paddingY: 2,
        paddingX: { xs: 1, md: 2 },
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
