import { Login as LoginIcon } from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useEffect, useReducer, useRef } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import ViseronLogo from "svg/viseron-logo.svg?react";

import { TextFieldItem, TextFieldItemState } from "components/TextFieldItem";
import { useAuthContext } from "context/AuthContext";
import { useTitle } from "hooks/UseTitle";
import { useAuthLogin } from "lib/api/auth";
import queryClient from "lib/api/client";
import { setManualLogout } from "lib/tokens";

type InputState = {
  username: TextFieldItemState;
  password: TextFieldItemState;
};

type InputAction = {
  type: keyof InputState;
  value: string;
};

const initialState: InputState = {
  username: { label: "Username", value: "", error: null },
  password: { label: "Password", value: "", error: null },
};

function reducer(state: InputState, action: InputAction): InputState {
  let error = null;
  if (!action.value) {
    error = "Required.";
  }

  return {
    ...state,
    [action.type]: { ...state[action.type], value: action.value, error },
  };
}

function Login() {
  useTitle("Login");
  const theme = useTheme();
  const { auth, user } = useAuthContext();
  const location = useLocation();
  const navigate = useNavigate();
  const login = useAuthLogin();

  const [inputState, dispatch] = useReducer(reducer, initialState);
  const fromRef = useRef(undefined);

  useEffect(() => {
    // Reset manual logout flag when entering login page
    setManualLogout(false);

    // Clean up queries when navigating to login page
    queryClient.removeQueries({
      predicate(query) {
        return query.queryKey[0] !== "auth" && query.queryKey[1] !== "enabled";
      },
    });
    queryClient.invalidateQueries({
      refetchType: "none",
      predicate(query) {
        return query.queryKey[0] !== "auth" && query.queryKey[1] !== "enabled";
      },
    });

    fromRef.current =
      location.state && location.state.from ? location.state.from : null;
    // Clear the state parameter
    if (fromRef.current) {
      navigate(location.pathname, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (auth.enabled && !auth.onboarding_complete) {
    return <Navigate to="/onboarding" />;
  }

  if (!auth.enabled) {
    return <Navigate to="/" />;
  }

  if (user) {
    return <Navigate to="/" />;
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        pt: "8vh",
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
                  transparent 4px,
                  rgba(0, 127, 255, 0.03) 4px,
                  rgba(0, 127, 255, 0.03) 8px
                ),
                repeating-linear-gradient(
                  90deg,
                  transparent,
                  transparent 4px,
                  rgba(0, 127, 255, 0.03) 4px,
                  rgba(0, 127, 255, 0.03) 8px
                )`
              : `repeating-linear-gradient(
                  0deg,
                  transparent,
                  transparent 4px,
                  rgba(0, 127, 255, 0.02) 4px,
                  rgba(0, 127, 255, 0.02) 8px
                ),
                repeating-linear-gradient(
                  90deg,
                  transparent,
                  transparent 4px,
                  rgba(0, 127, 255, 0.02) 4px,
                  rgba(0, 127, 255, 0.02) 8px
                )`,
          backgroundSize: "150px 150px",
          opacity: 0.5,
          pointerEvents: "none",
        },
      }}
    >
      <Container maxWidth="sm" sx={{ position: "relative", zIndex: 1 }}>
        <Stack spacing={4} alignItems="center">
          {/* Logo and Brand Section */}
          <Box
            sx={{
              textAlign: "center",
            }}
          >
            <Box
              sx={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
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
            <Typography
              variant="h4"
              sx={{
                color: "text.primary",
              }}
            >
              Viseron Login
            </Typography>
          </Box>

          {/* Login Form */}
          <Paper
            elevation={8}
            sx={{
              width: "100%",
              maxWidth: 400,
              borderRadius: 2,
              overflow: "hidden",
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
            <Box sx={{ p: 4 }}>
              {login.error && (
                <Box
                  sx={{
                    p: 2,
                    mb: 3,
                    borderRadius: 2,
                    backgroundColor: `${theme.palette.error.main}10`,
                    border: `1px solid ${theme.palette.error.main}30`,
                  }}
                >
                  <Typography
                    variant="body2"
                    align="center"
                    sx={{
                      color: "error.main",
                      fontWeight: 500,
                    }}
                  >
                    {login.error.response &&
                    login.error.response.data.status === 401
                      ? "Incorrect username or password"
                      : "An error occurred. Please try again."}
                  </Typography>
                </Box>
              )}

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                }}
              >
                <Stack spacing={3} sx={{ mt: 2 }}>
                  <TextFieldItem<keyof InputState>
                    inputKind="username"
                    inputState={inputState}
                    dispatch={dispatch}
                    value={inputState.username.value}
                  />
                  <TextFieldItem<keyof InputState>
                    inputKind="password"
                    inputState={inputState}
                    dispatch={dispatch}
                    password
                  />

                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    startIcon={<LoginIcon size={16} />}
                    size="large"
                    disabled={
                      !inputState.username.value ||
                      !inputState.password.value ||
                      !!inputState.username.error ||
                      !!inputState.password.error ||
                      login.isPending
                    }
                    onClick={() => {
                      login.mutate(
                        {
                          username: inputState.username.value,
                          password: inputState.password.value,
                        },
                        {
                          onSuccess: async (_data, _variables, _context) => {
                            // Wait for backend to set cookie
                            await new Promise((resolve) => {
                              setTimeout(resolve, 100);
                            });

                            window.location.href = "/";
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
                      mt: 2,
                      boxShadow: 2,
                      "&:hover": {
                        boxShadow: 4,
                      },
                      "&:disabled": {
                        boxShadow: 0,
                      },
                    }}
                  >
                    {login.isPending ? "SIGNING IN..." : "SIGN IN"}
                  </Button>
                </Stack>
              </form>
            </Box>
          </Paper>
        </Stack>
      </Container>
    </Box>
  );
}

export default Login;
