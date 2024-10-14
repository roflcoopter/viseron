import NavigateNextIcon from "@mui/icons-material/NavigateNext";
import MuiBreadcrumbs from "@mui/material/Breadcrumbs";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { Link as RouterLink, useLocation } from "react-router-dom";

import queryClient from "lib/api/client";
import { toTitleCase } from "lib/helpers";
import * as types from "lib/types";

export default function Breadcrumbs() {
  const theme = useTheme();
  const mediaQuerySmall = useMediaQuery(theme.breakpoints.up("sm"));
  const location = useLocation();
  const pathnames = location.pathname.split("/").filter((x) => x);
  if (pathnames.length === 0) {
    pathnames.push("cameras");
  }

  if (!mediaQuerySmall) {
    return (
      <Typography color="textPrimary" align="center" style={{ width: "100%" }}>
        {toTitleCase(pathnames[0])}
      </Typography>
    );
  }

  return (
    <MuiBreadcrumbs
      maxItems={4}
      separator={<NavigateNextIcon fontSize="small" />}
      aria-label="Breadcrumb"
    >
      <Typography color="textPrimary" />
      {pathnames.map((value: any, index: number) => {
        const last = index === pathnames.length - 1;
        const to = `/${pathnames.slice(0, index + 1).join("/")}`;
        const camera = queryClient.getQueryData<types.Camera>([
          "camera",
          value,
        ]);
        if (camera) {
          value = camera.name;
        }

        return last ? (
          <Typography color="textPrimary" key={to}>
            {toTitleCase(value)}
          </Typography>
        ) : (
          <Link
            underline="hover"
            color="inherit"
            component={RouterLink}
            to={to}
            key={to}
          >
            {toTitleCase(value)}
          </Link>
        );
      })}
    </MuiBreadcrumbs>
  );
}
