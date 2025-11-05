import { 
  LogoGithub,
} from "@carbon/icons-react";
import Box from "@mui/material/Box";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { styled, useTheme } from "@mui/material/styles";
import { useContext } from "react";
import { useLocation } from "react-router-dom";

import { ViseronContext } from "context/ViseronContext";

const Footer = styled("footer")(() => ({
  position: "relative",
  left: 0,
  bottom: 0,
  marginTop: "100px",
  paddingBottom: "35px",
}));

export default function AppFooter() {
  const theme = useTheme();
  const location = useLocation();
  const { version, gitCommit } = useContext(ViseronContext);
  const showFooter = !["/configuration", "/events", "/live"].includes(
    location.pathname,
  );

  return showFooter ? (
    <Footer>
      <Typography
        align="center"
        variant="subtitle2"
        color={theme.palette.text.secondary}
      >
        Viseron - {version} - {gitCommit}
      </Typography>
      <Typography align="center">
        <Link
          target="_blank"
          href="https://github.com/roflcoopter/viseron"
          color={theme.palette.text.secondary}
          fontSize={17}
        >
          <Box
            sx={{
              verticalAlign: "middle",
              marginRight: "5px",
              display: "inline-block",
            }}
          >
            <LogoGithub size={17}/>
          </Box>
          GitHub
        </Link>
      </Typography>
    </Footer>
  ) : null;
}
