import PrivateLayout from "layouts/PrivateLayout";
import { lazy } from "react";
import { Navigate, useRoutes } from "react-router-dom";
import "react-toastify/dist/ReactToastify.css";

const Cameras = lazy(() => import("pages/Cameras"));
const CameraRecordings = lazy(
  () => import("pages/recordings/CameraRecordings")
);
const CameraRecordingsDaily = lazy(
  () => import("pages/recordings/CameraRecordingsDaily")
);
const Configuration = lazy(() => import("pages/Configuration"));
const Entities = lazy(() => import("pages/Entities"));
const Events = lazy(() => import("pages/Events"));
const Login = lazy(() => import("pages/Login"));
const NotFound = lazy(() => import("pages/NotFound"));
const Onboarding = lazy(() => import("pages/Onboarding"));
const PublicLayout = lazy(() => import("layouts/PublicLayout"));
const Recordings = lazy(() => import("pages/recordings/Recordings"));

function App() {
  const routes = useRoutes([
    {
      element: <PrivateLayout />,
      children: [
        {
          path: "/cameras",
          element: <Navigate to="/" replace />,
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
          path: "/configuration",
          element: <Configuration />,
        },
        {
          path: "/entities",
          element: <Entities />,
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
