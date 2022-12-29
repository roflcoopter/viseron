import NavigateNextIcon from "@mui/icons-material/NavigateNext";
import MuiBreadcrumbs from "@mui/material/Breadcrumbs";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { useContext } from "react";
import { Link as RouterLink, useLocation } from "react-router-dom";

import { ViseronContext } from "context/ViseronContext";
import { toTitleCase } from "lib/helpers";

export default function Breadcrumbs() {
  const viseron = useContext(ViseronContext);
  const location = useLocation();
  const pathnames = location.pathname.split("/").filter((x) => x);
  if (pathnames.length === 0) {
    return null;
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
        if (value in viseron.cameras) {
          value = viseron.cameras[value].name;
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
