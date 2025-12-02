import PrivateLayout, { RequireRole } from "layouts/PrivateLayout";
import { lazy } from "react";
import { Navigate, useRoutes } from "react-router-dom";

const Cameras = lazy(() => import("pages/Cameras"));
const Tuning = lazy(() => import("pages/Tuning"));
const CameraRecordings = lazy(
  () => import("pages/recordings/CameraRecordings"),
);
const CameraRecordingsDaily = lazy(
  () => import("pages/recordings/CameraRecordingsDaily"),
);
const Configuration = lazy(() => import("pages/Configuration"));
const Entities = lazy(() => import("pages/Entities"));
const Events = lazy(() => import("pages/Events"));
const Login = lazy(() => import("pages/Login"));
const Live = lazy(() => import("pages/Live"));
const NotFound = lazy(() => import("pages/NotFound"));
const Onboarding = lazy(() => import("pages/Onboarding"));
const PublicLayout = lazy(() => import("layouts/PublicLayout"));
const Recordings = lazy(() => import("pages/recordings/Recordings"));
const Settings = lazy(() => import("pages/settings"));
const SystemEvents = lazy(() => import("pages/settings/SystemEvents"));
const Users = lazy(() => import("pages/settings/Users"));
const TemplateEditor = lazy(() => import("pages/settings/TemplateEditor"));

function App() {
  const routes = useRoutes([
    {
      element: <PrivateLayout />,
      children: [
        {
          element: <RequireRole userRole={["admin"]} />,
          children: [
            {
              path: "/cameras",
              children: [
                { index: true, element: <Navigate to="/" replace /> },
                {
                  path: ":camera_identifier",
                  children: [{ index: true, element: <Tuning /> }],
                },
              ],
            },
          ],
        },
        {
          path: "/",
          element: <Cameras />,
        },
        {
          path: "/recordings",
          children: [
            { index: true, element: <Recordings /> },
            {
              path: ":camera_identifier",
              children: [
                { index: true, element: <CameraRecordings /> },
                {
                  path: ":date",
                  element: <CameraRecordingsDaily />,
                },
              ],
            },
          ],
        },
        {
          path: "/events",
          element: <Events />,
        },
        {
          path: "/live",
          element: <Live />,
        },
        {
          path: "/entities",
          element: <Entities />,
        },
        {
          element: <RequireRole userRole={["admin"]} />,
          children: [
            {
              path: "/settings",
              children: [
                { index: true, element: <Settings /> },
                {
                  path: "/settings/configuration",
                  element: <Configuration />,
                },
                {
                  path: "/settings/users",
                  element: <Users />,
                },
                {
                  path: "/settings/system-events",
                  element: <SystemEvents />,
                },
                {
                  path: "/settings/template-editor",
                  element: <TemplateEditor />,
                },
              ],
            },
          ],
        },
      ],
    },
    {
      element: <PublicLayout />,
      children: [
        {
          path: "/login",
          element: <Login />,
        },
        {
          path: "/onboarding",
          element: <Onboarding />,
        },
      ],
    },
    {
      path: "*",
      element: <NotFound />,
    },
  ]);

  return routes;
}

export default App;
