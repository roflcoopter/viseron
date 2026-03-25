import { QueryClient } from "@tanstack/react-query";
import axios from "axios";

// Detect base path from the current URL for subpath support
// If running at /viseron/index.html, basePath will be /viseron
// If running at /index.html, basePath will be empty
function getBasePath(): string {
  const path = window.location.pathname;
  return path.substring(0, path.lastIndexOf("/"));
}

export const BASE_PATH = getBasePath();
export const API_V1_URL = `${BASE_PATH}/api/v1`;
export const viseronAPI = axios.create({
  baseURL: API_V1_URL,
  // Match Tornado XSRF protection
  xsrfCookieName: "_xsrf",
  xsrfHeaderName: "X-Xsrftoken",
  headers: {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
  },
});
export const clientId = (): string =>
  `${location.protocol}//${location.host}${BASE_PATH}/`;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 1,
      gcTime: 1000 * 60 * 5,
      queryFn: async ({ queryKey: [url] }) => {
        if (typeof url === "string") {
          const response = await viseronAPI.get(`${url.toLowerCase()}`);
          return response.data;
        }
        throw new Error("Invalid QueryKey");
      },
    },
  },
});

export default queryClient;
