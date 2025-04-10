import { DeferredPromise } from "@open-draft/deferred-promise";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import Cookies from "js-cookie";
import { HttpResponse, http } from "msw";
import { useLayoutEffect } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { API_BASE_URL } from "tests/mocks/handlers";
import { server } from "tests/mocks/server";
import { vi } from "vitest";

import { AuthProvider, useAuthContext } from "context/AuthContext";

function TestComponent() {
  const { auth, user } = useAuthContext();
  return (
    <div>
      <p data-testid="auth-enabled">{auth.enabled?.toString()}</p>
      <p data-testid="user-name">{user?.name || "No user"}</p>
    </div>
  );
}

describe("AuthContext", () => {
  // Use custom renderer since renderWithContext does not render the actual provider
  const renderWithProviders = (ui: React.ReactNode) => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AuthProvider>{ui}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  };

  beforeEach(() => {
    cleanup();

    vi.clearAllMocks();
    Cookies.get = vi.fn((name?: string) => {
      const cookies: Record<string, string> = { user: "123456789" };
      if (name) {
        return cookies[name];
      }
      return cookies; // Return the entire cookies object when no name is provided
    }) as unknown as typeof Cookies.get;
  });

  afterEach(() => {
    cleanup();
  });

  it("renders loading state while fetching auth data", async () => {
    const responsePromise = new DeferredPromise();
    server.use(
      http.get(
        `${API_BASE_URL}/auth/user/123456789`,
        async () => {
          await responsePromise;
          return new HttpResponse("Test", { status: 200 });
        },
        { once: true },
      ),
    );
    renderWithProviders(<TestComponent />);
    await waitFor(() => {
      expect(screen.getByText("Loading Auth")).toBeInTheDocument();
    });
    responsePromise.resolve(null);
  });

  it("renders error message when auth query fails", async () => {
    // Simulate server error response
    server.use(
      http.get(
        `${API_BASE_URL}/auth/enabled`,
        () => HttpResponse.json({ error: "Server error" }, { status: 500 }),
        { once: true },
      ),
    );

    renderWithProviders(<TestComponent />);
    await waitFor(() => {
      expect(
        screen.getByText("Error connecting to server"),
      ).toBeInTheDocument();
    });
  });

  it("renders loading state while fetching user data", async () => {
    // Simulate slow call to fetch user
    const responsePromise = new DeferredPromise();
    server.use(
      http.get(
        `${API_BASE_URL}/auth/user/123456789`,
        async () => {
          await responsePromise;
          return new HttpResponse("Test", { status: 200 });
        },
        { once: true },
      ),
    );

    renderWithProviders(<TestComponent />);
    await waitFor(() => {
      expect(screen.getByText("Loading User")).toBeInTheDocument();
    });
    responsePromise.resolve(null);
  });

  it("renders error message when user query fails", async () => {
    // Simulate server error response
    server.use(
      http.get(
        `${API_BASE_URL}/auth/user/123456789`,
        () => HttpResponse.json({ error: "Server error" }, { status: 500 }),
        { once: true },
      ),
    );

    renderWithProviders(<TestComponent />);
    await waitFor(() => {
      expect(screen.getByText("Error loading user")).toBeInTheDocument();
    });
  });

  it("navigates to onboarding when auth is enabled but onboarding is not complete", async () => {
    // Override the default mock for /auth/enabled to return onboarding_complete: false
    server.use(
      http.get(
        `${API_BASE_URL}/auth/enabled`,
        () =>
          HttpResponse.json(
            { enabled: true, onboarding_complete: false },
            { status: 200 },
          ),
        { once: true },
      ),
    );

    // Create a wrapper component that will detect navigation
    const navigationDetector = vi.fn();

    function NavigationTestWrapper() {
      const location = useLocation();

      // Use an effect to track location changes
      useLayoutEffect(() => {
        navigationDetector(location.pathname);
      }, [location]);

      return (
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );
    }

    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <NavigationTestWrapper />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Wait for the navigation to be detected
    await waitFor(() => {
      expect(navigationDetector).toHaveBeenCalledWith("/onboarding");
    });
  });

  it("provides auth and user data when queries succeed", async () => {
    renderWithProviders(<TestComponent />);
    await waitFor(() => {
      expect(screen.getByTestId("auth-enabled").textContent).toBe("true");
      expect(screen.getByTestId("user-name").textContent).toBe("Test User");
    });
  });
});
