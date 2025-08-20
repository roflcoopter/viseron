import CssBaseline from "@mui/material/CssBaseline";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RenderHookOptions,
  RenderOptions,
  render,
  renderHook,
} from "@testing-library/react";
import { useRef } from "react";
import { MemoryRouter } from "react-router-dom";

import ToastContainer from "components/toast/ToastContainer";
import { AuthContext } from "context/AuthContext";
import { ColorModeProvider } from "context/ColorModeContext";
import { ViseronContext, ViseronContextState } from "context/ViseronContext";
import * as types from "lib/types";

interface ProvidersWrapperProps {
  children?: React.ReactNode;
}

// Wraps a component in all the providers needed for testing
export interface TestContextOptions {
  auth?: types.AuthEnabledResponse;
  user?: types.AuthUserResponse | null;
  queryClient?: QueryClient;
  connection?: ViseronContextState["connection"];
  viseronOverrides?: Partial<ViseronContextState>;
}

const defaultAuth: types.AuthEnabledResponse = {
  enabled: true,
  onboarding_complete: true,
};

const defaultUser: types.AuthUserResponse = {
  id: "123456789",
  name: "",
  username: "",
  role: "admin",
  assigned_cameras: null,
};

export function createProvidersWrapper(options: TestContextOptions = {}) {
  const {
    auth = defaultAuth,
    user = defaultUser,
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    }),
    connection = undefined,
    viseronOverrides = {},
  } = options;

  function ProvidersWrapper({ children }: ProvidersWrapperProps) {
    const viseronValue: ViseronContextState = {
      connected: true,
      safeMode: false,
      version: "0.0.0",
      gitCommit: "0000000",
      subscriptionRef: useRef({}),
      ...viseronOverrides,
      connection:
        connection !== undefined ? connection : viseronOverrides.connection,
    };

    return (
      <ColorModeProvider>
        <CssBaseline enableColorScheme />
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <AuthContext.Provider value={{ auth, user }}>
              <ViseronContext.Provider value={viseronValue}>
                {children}
              </ViseronContext.Provider>
            </AuthContext.Provider>
          </MemoryRouter>
          <ToastContainer />
        </QueryClientProvider>
      </ColorModeProvider>
    );
  }
  return ProvidersWrapper;
}

// Component render helper
function renderWithContext(
  component: React.ReactElement,
  options?: TestContextOptions & Omit<RenderOptions, "wrapper">,
) {
  const { viseronOverrides, connection, auth, user, queryClient, ...rtl } =
    options || {};
  const wrapper = createProvidersWrapper({
    viseronOverrides,
    connection,
    auth,
    user: user || null,
    queryClient,
  });
  return render(component, { wrapper, ...rtl });
}

// Hook render helper
function renderHookWithContext<TProps, TResult>(
  callback: (initialProps: TProps) => TResult,
  options?: TestContextOptions &
    RenderHookOptions<TProps> & { initialProps?: TProps },
) {
  const {
    viseronOverrides,
    connection,
    auth,
    user,
    queryClient,
    initialProps,
    ...rest
  } = options || ({} as any);
  const wrapper = createProvidersWrapper({
    viseronOverrides,
    connection,
    auth,
    user: user || null,
    queryClient,
  });
  return renderHook(callback, { wrapper, initialProps, ...rest });
}

export { renderWithContext, renderHookWithContext };
