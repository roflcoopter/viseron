import { AddFilled } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { Navigate } from "react-router-dom";
import ViseronLogo from "svg/viseron-logo.svg?react";

import { TextFieldItem } from "components/TextFieldItem";
import { useAuthContext } from "context/AuthContext";
import { useTitle } from "hooks/UseTitle";
import { InputState, useUserForm } from "hooks/UseUserForm";
import queryClient from "lib/api/client";
import { useOnboarding } from "lib/api/onboarding";

function Onboarding() {
  useTitle("Onboarding");
  const theme = useTheme();
  const { auth } = useAuthContext();
  const { inputState, dispatch, isFormValid } = useUserForm(false);
  const onboarding = useOnboarding();

  if ((auth.enabled && auth.onboarding_complete) || !auth.enabled) {
    return <Navigate to="/" />;
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        pb: "8vh",
        px: 2,
        position: "relative",
        overflow: "hidden",
        background:
          theme.palette.mode === "dark"
            ? "linear-gradient(135deg, #0A1929 0%, #001E3C 50%, #0A1929 100%)"
            : "linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 50%, #E3F2FD 100%)",
        "&::before": {
          content: '""',
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundImage:
            theme.palette.mode === "dark"
              ? `radial-gradient(circle at 20% 50%, rgba(0, 127, 255, 0.1) 0%, transparent 50%),
                 radial-gradient(circle at 80% 80%, rgba(0, 127, 255, 0.08) 0%, transparent 50%),
                 radial-gradient(circle at 40% 20%, rgba(0, 127, 255, 0.06) 0%, transparent 50%)`
              : `radial-gradient(circle at 20% 50%, rgba(0, 127, 255, 0.08) 0%, transparent 50%),
                 radial-gradient(circle at 80% 80%, rgba(0, 127, 255, 0.06) 0%, transparent 50%),
                 radial-gradient(circle at 40% 20%, rgba(0, 127, 255, 0.04) 0%, transparent 50%)`,
          pointerEvents: "none",
        },
        "&::after": {
          content: '""',
          position: "absolute",
          top: "-50%",
          left: "-50%",
          width: "200%",
          height: "200%",
          backgroundImage:
            theme.palette.mode === "dark"
              ? `repeating-linear-gradient(
                  0deg,
                  transparent,
                  transparent 2px,
                  rgba(0, 127, 255, 0.03) 2px,
                  rgba(0, 127, 255, 0.03) 4px
                ),
                repeating-linear-gradient(
                  90deg,
                  transparent,
                  transparent 2px,
                  rgba(0, 127, 255, 0.03) 2px,
                  rgba(0, 127, 255, 0.03) 4px
                )`
              : `repeating-linear-gradient(
                  0deg,
                  transparent,
                  transparent 2px,
                  rgba(0, 127, 255, 0.02) 2px,
                  rgba(0, 127, 255, 0.02) 4px
                ),
                repeating-linear-gradient(
                  90deg,
                  transparent,
                  transparent 2px,
                  rgba(0, 127, 255, 0.02) 2px,
                  rgba(0, 127, 255, 0.02) 4px
                )`,
          backgroundSize: "100px 100px",
          opacity: 0.5,
          pointerEvents: "none",
        },
      }}
    >
      <Container maxWidth="sm" sx={{ position: "relative", zIndex: 1 }}>
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          sx={{
            width: 150,
            height: 150,
            margin: "0 auto",
            "& > *": {
              animation: "viseron-slow-spin 30s linear infinite",
              transformOrigin: "center center",
              display: "block",
            },
            "@keyframes viseron-slow-spin": {
              "0%": { transform: "rotate(0deg)" },
              "100%": { transform: "rotate(360deg)" },
            },
          }}
        >
          <ViseronLogo width={150} height={150} />
        </Box>
        <Typography variant="h4" align="center">
          Welcome to Viseron!
        </Typography>
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          sx={{ marginTop: "25px" }}
        >
          <Paper
            sx={{
              paddingTop: "5px",
              width: "95%",
              maxWidth: 600,
              py: 2,
              px: 2,
              borderRadius: 2,
              border: `1px solid ${
                theme.palette.mode === "dark"
                  ? "rgba(255, 255, 255, 0.1)"
                  : "rgba(255, 255, 255, 0.3)"
              }`,
              backgroundColor:
                theme.palette.mode === "dark"
                  ? "rgba(12, 30, 48, 0.7)"
                  : "rgba(255, 255, 255, 0.7)",
              backdropFilter: "blur(20px) saturate(50%)",
              WebkitBackdropFilter: "blur(20px) saturate(180%)",
              boxShadow:
                theme.palette.mode === "dark"
                  ? "0px 8px 32px rgba(0, 0, 0, 0.4), inset 0px 1px 0px rgba(255, 255, 255, 0.1)"
                  : "0px 8px 32px rgba(0, 0, 0, 0.1), inset 0px 1px 0px rgba(255, 255, 255, 0.8)",
            }}
          >
            <Typography
              variant="h6"
              align="center"
              sx={{ paddingBottom: "15px", paddingTop: "5px" }}
            >
              Create an Account
            </Typography>
            {onboarding.isError ? (
              <Typography variant="h6" align="center" color="error">
                {onboarding.error?.response?.data.error}
              </Typography>
            ) : null}
            <form
              onSubmit={(e) => {
                e.preventDefault();
              }}
            >
              <Grid container spacing={3} sx={{ padding: "15px" }}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextFieldItem<keyof InputState>
                    autoFocus
                    inputKind="displayName"
                    inputState={inputState}
                    dispatch={dispatch}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextFieldItem<keyof InputState>
                    inputKind="username"
                    inputState={inputState}
                    dispatch={dispatch}
                    value={inputState.username.value}
                    onFocus={() => {
                      if (!inputState.username.value) {
                        dispatch({
                          type: "username",
                          value: inputState.displayName.value.toLowerCase(),
                        });
                      }
                    }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextFieldItem<keyof InputState>
                    inputKind="password"
                    inputState={inputState}
                    dispatch={dispatch}
                    password
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextFieldItem<keyof InputState>
                    inputKind="confirmPassword"
                    inputState={inputState}
                    dispatch={dispatch}
                    password
                  />
                </Grid>
                <Grid size={12}>
                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    startIcon={<AddFilled size={16} />}
                    disabled={!isFormValid() || onboarding.isPending}
                    onClick={() => {
                      onboarding.mutate(
                        {
                          name: inputState.displayName.value,
                          username: inputState.username.value,
                          password: inputState.password.value,
                        },
                        {
                          onSuccess: async () => {
                            // Invalidate auth query to force a re-fetch, which will redirect to the dashboard
                            await queryClient.invalidateQueries({
                              queryKey: ["auth"],
                            });
                          },
                        },
                      );
                    }}
                    sx={{
                      py: 1.5,
                      borderRadius: 2,
                      textTransform: "none",
                      fontSize: "1rem",
                      fontWeight: 600,
                      boxShadow: 2,
                      "&:hover": {
                        boxShadow: 4,
                      },
                      "&:disabled": {
                        boxShadow: 0,
                      },
                    }}
                  >
                    SIGN UP
                  </Button>
                </Grid>
              </Grid>
            </form>
          </Paper>
        </Box>
      </Container>
    </Box>
  );
}

export default Onboarding;
