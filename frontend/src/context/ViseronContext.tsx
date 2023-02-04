import { AxiosHeaders } from "axios";
import React, {
  FC,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useQueryClient } from "react-query";

import { authToken } from "lib/api/auth";
import { clientId, viseronAPI } from "lib/api/client";
import { loadTokens } from "lib/api/tokens";
import { getCameras, subscribeCameras, subscribeRecording } from "lib/commands";
import { sortObj } from "lib/helpers";
import * as types from "lib/types";
import { Connection } from "lib/websockets";

export type ViseronProviderProps = {
  children: React.ReactNode;
};

export type ViseronContextState = {
  user: boolean;
  setUser: React.Dispatch<React.SetStateAction<boolean>>;
  connection: Connection | undefined;
  connected: boolean;
  cameras: types.Cameras;
};

const contextDefaultValues: ViseronContextState = {
  user: false,
  setUser: () => {},
  connection: undefined,
  connected: false,
  cameras: {},
};

export const ViseronContext =
  createContext<ViseronContextState>(contextDefaultValues);

export const useUser = () => {
  const viseron = useContext(ViseronContext);
  return { user: viseron.user, setUser: viseron.setUser };
};

let isFetchingTokens = false;
let tokenPromise: Promise<types.AuthTokenResponse>;

export const ViseronProvider: FC<ViseronProviderProps> = ({
  children,
}: ViseronProviderProps) => {
  const [connection, setConnection] = useState<Connection | undefined>(
    undefined
  );
  const [connected, setConnected] = useState<boolean>(false);
  const [cameras, setCameras] = useState<types.Cameras>({});
  const [user, setUser] = useState<boolean>(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (connection) {
      const cameraRegistered = async (camera: types.Camera) => {
        setCameras((prevCameras) => {
          let newCameras = { ...prevCameras };
          newCameras[camera.identifier] = camera;
          newCameras = sortObj(newCameras);
          return newCameras;
        });
        await queryClient.invalidateQueries({
          predicate: (query) =>
            (query.queryKey[0] as string).startsWith(
              `/recordings/${camera.identifier}`
            ),
        });
      };
      const newRecording = async (
        recordingEvent: types.EventRecorderComplete
      ) => {
        await queryClient.invalidateQueries({
          predicate: (query) =>
            (query.queryKey[0] as string).startsWith(
              `/recordings/${recordingEvent.data.camera.identifier}`
            ),
        });
      };

      const onConnect = async () => {
        setConnected(true);
        const registeredCameras = await getCameras(connection);
        setCameras(sortObj(registeredCameras));
      };
      connection.addEventListener("connected", onConnect);

      const onDisonnect = async () => {
        setConnected(false);
      };
      connection.addEventListener("disconnected", onDisonnect);

      const connect = async () => {
        subscribeCameras(connection, cameraRegistered); // call without await to not block
        subscribeRecording(connection, newRecording); // call without await to not block
        await connection.connect();
      };
      connect();
    }
  }, [connection, queryClient]);

  useMemo(() => {
    viseronAPI.interceptors.request.use(async (config) => {
      // Bypass refreshing tokens for login to avoid deadlock in await
      if (config.url?.includes("/auth/token")) {
        return config;
      }

      let storedTokens = loadTokens();

      // Refresh tokens if they expire within 10 seconds
      if (Date.now() - 10000 > storedTokens.expires_at) {
        if (!isFetchingTokens) {
          isFetchingTokens = true;
          tokenPromise = authToken({
            grant_type: "refresh_token",
            refresh_token: storedTokens.refresh_token,
            client_id: clientId(),
          });
        }
        await tokenPromise;
        isFetchingTokens = false;
        // Load the new tokens
        storedTokens = loadTokens();
      }

      if (storedTokens) {
        (config.headers as AxiosHeaders).set(
          "Authorization",
          `Bearer ${storedTokens.access_token}`
        );
      }
      return config;
    });

    viseronAPI.interceptors.response.use(
      async (res) => res,
      async (error) => {
        const originalRequest = error.config;
        const status = error.response.status;

        if (
          (status === 401 || status === 403) &&
          !originalRequest._visRetry &&
          !originalRequest.url.includes("/auth")
        ) {
          const storedTokens = loadTokens();
          // if (!storedTokens || !objHasValues(storedTokens)) {
          //   console.log("Tokens not found, redirecting to login");
          //   navigate("/login");
          //   return Promise.reject(error);
          // }
          if (!isFetchingTokens) {
            isFetchingTokens = true;
            tokenPromise = authToken({
              grant_type: "refresh_token",
              refresh_token: storedTokens.refresh_token,
              client_id: clientId(),
            });
          }
          const tokens = await tokenPromise;
          isFetchingTokens = false;

          originalRequest._visRetry = true;
          originalRequest.headers.authorization = `Bearer ${tokens.access_token}`;
          return viseronAPI(originalRequest);
        }
        if ((status === 401 || status === 403) && originalRequest._visRetry) {
          setUser(false);
        }
        return Promise.reject(error);
      }
    );
  }, []);

  useEffect(() => {
    setConnection(new Connection());
  }, []);

  return (
    <ViseronContext.Provider
      value={{ user, setUser, connection, connected, cameras }}
    >
      {children}
    </ViseronContext.Provider>
  );
};
