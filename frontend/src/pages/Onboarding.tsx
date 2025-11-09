import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
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
  const { auth } = useAuthContext();
  const { inputState, dispatch, isFormValid } = useUserForm(false);
  const onboarding = useOnboarding();

  if ((auth.enabled && auth.onboarding_complete) || !auth.enabled) {
    return <Navigate to="/" />;
  }

  return (
    <Box
      sx={{
        minHeight: "90vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        py: 2,
        px: 2,
      }}
    >
      <Container sx={{ marginTop: "2%" }}>
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
            }}
          >
            <Typography variant="h6" align="center" sx={{ padding: "10px" }}>
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
