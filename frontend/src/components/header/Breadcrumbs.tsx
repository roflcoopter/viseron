import { ChevronRight } from "@carbon/icons-react";
import MuiBreadcrumbs from "@mui/material/Breadcrumbs";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { Link as RouterLink, useLocation } from "react-router-dom";

import { getCameraNameFromQueryCache, toTitleCase } from "lib/helpers";

const getTitle = (str: string) => toTitleCase(str.replace("-", " "));

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
        {getTitle(pathnames[0])}
      </Typography>
    );
  }

  return (
    <MuiBreadcrumbs
      maxItems={4}
      separator={<ChevronRight size={20}/>}
      aria-label="Breadcrumb"
    >
      <Typography color="textPrimary" />
      {pathnames.map((value: any, index: number) => {
        const last = index === pathnames.length - 1;
        const to = `/${pathnames.slice(0, index + 1).join("/")}`;
        const cameraName = getCameraNameFromQueryCache(value);
        if (cameraName) {
          value = cameraName;
        }

        return last ? (
          <Typography color="textPrimary" key={to}>
            {getTitle(value)}
          </Typography>
        ) : (
          <Link
            underline="hover"
            color="inherit"
            component={RouterLink}
            to={to}
            key={to}
          >
            {getTitle(value)}
          </Link>
        );
      })}
    </MuiBreadcrumbs>
  );
}
