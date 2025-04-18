import CssBaseline from "@mui/material/CssBaseline";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RenderOptions, render } from "@testing-library/react";
import { useRef } from "react";
import { MemoryRouter } from "react-router-dom";

import ToastContainer from "components/toast/ToastContainer";
import { AuthContext } from "context/AuthContext";
import { ColorModeProvider } from "context/ColorModeContext";
import { ViseronContext } from "context/ViseronContext";
import * as types from "lib/types";

interface ProvidersWrapperProps {
  children?: React.ReactNode;
}

// Wraps a component in all the providers needed for testing
function customRender(
  component: React.ReactElement,
  auth: types.AuthEnabledResponse = {
    enabled: true,
    onboarding_complete: true,
  },
  user: types.AuthUserResponse | null = {
    id: "123456789",
    name: "",
    username: "",
    role: "admin",
    assigned_cameras: null,
  },
  queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  }),
  options?: Omit<RenderOptions, "wrapper">,
) {
  function ProvidersWrapper({ children }: ProvidersWrapperProps) {
    return (
      <ColorModeProvider>
        <CssBaseline enableColorScheme />
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <AuthContext.Provider
              value={{
                auth,
                user,
              }}
            >
              <ViseronContext.Provider
                value={{
                  connection: undefined,
                  connected: true,
                  safeMode: false,
                  version: "0.0.0",
                  gitCommit: "0000000",
                  subscriptionRef: useRef({}),
                }}
              >
                {children}
              </ViseronContext.Provider>
            </AuthContext.Provider>
          </MemoryRouter>
          <ToastContainer />
        </QueryClientProvider>
      </ColorModeProvider>
    );
  }

  return render(component, { wrapper: ProvidersWrapper, ...options });
}

export { customRender as renderWithContext };
