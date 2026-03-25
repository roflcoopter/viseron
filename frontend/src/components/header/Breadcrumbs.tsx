import { ChevronRight } from "@carbon/icons-react";
import MuiBreadcrumbs from "@mui/material/Breadcrumbs";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { Link as RouterLink, useLocation } from "react-router-dom";

import { capitalizeEachWord, getCameraNameFromQueryCache } from "lib/helpers";
import { isDateFormat } from "lib/helpers/dates";

export default function Breadcrumbs() {
  const theme = useTheme();
  const mediaQuerySmall = useMediaQuery(theme.breakpoints.up("sm"));
  const location = useLocation();
  const pathnames = location.pathname.split("/").filter((x) => x);
  if (pathnames.length === 0) {
    pathnames.push("cameras");
  }

  if (!mediaQuerySmall) {
    const cameraName = getCameraNameFromQueryCache(pathnames[0]);
    const displayValue = cameraName || pathnames[0];
    // Only capitalize if it's not a camera name or date
    const shouldCapitalize =
      (!cameraName || cameraName === pathnames[0]) &&
      !isDateFormat(pathnames[0]);
    return (
      <Typography color="textPrimary" sx={{ width: "100%" }}>
        {shouldCapitalize ? capitalizeEachWord(displayValue) : displayValue}
      </Typography>
    );
  }

  return (
    <MuiBreadcrumbs
      maxItems={4}
      separator={<ChevronRight size={20} />}
      aria-label="Breadcrumb"
    >
      <Typography color="textPrimary" />
      {pathnames.map((value: any, index: number) => {
        const last = index === pathnames.length - 1;
        const to = `/${pathnames.slice(0, index + 1).join("/")}`;

        // Use camera name if available, otherwise use original value
        const cameraName = getCameraNameFromQueryCache(value);
        const displayText = cameraName || value;

        // Only capitalize if it's not a camera name or date
        const shouldCapitalize =
          (!cameraName || cameraName === value) && !isDateFormat(value);
        const displayValue = shouldCapitalize
          ? capitalizeEachWord(displayText)
          : displayText;

        return last ? (
          <Typography color="textPrimary" key={to}>
            {displayValue}
          </Typography>
        ) : (
          <Link
            underline="hover"
            color="inherit"
            component={RouterLink}
            to={to}
            key={to}
          >
            {displayValue}
          </Link>
        );
      })}
    </MuiBreadcrumbs>
  );
}
