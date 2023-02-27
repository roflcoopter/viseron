import PrivateLayout from "layouts/PrivateLayout";
import PublicLayout from "layouts/PublicLayout";
import { lazy } from "react";
import { Navigate, useRoutes } from "react-router-dom";
import "react-toastify/dist/ReactToastify.css";

import Cameras from "pages/Cameras";
import CameraRecordings from "pages/recordings/CameraRecordings";
import CameraRecordingsDaily from "pages/recordings/CameraRecordingsDaily";
import Recordings from "pages/recordings/Recordings";

const Configuration = lazy(() => import("pages/Configuration"));
const Entities = lazy(() => import("pages/Entities"));
const Login = lazy(() => import("pages/Login"));
const Onboarding = lazy(() => import("pages/Onboarding"));

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
  ]);

  return routes;
}

export default App;
