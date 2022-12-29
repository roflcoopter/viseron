import GitHubIcon from "@mui/icons-material/GitHub";
import { Typography, useTheme } from "@mui/material";
import Link from "@mui/material/Link";
import { styled } from "@mui/material/styles";

const Footer = styled("footer")(() => ({
  position: "relative",
  left: 0,
  bottom: 0,
  marginTop: "100px",
  paddingBottom: "35px",
}));

export default function AppFooter() {
  const theme = useTheme();

  return (
    <Footer>
      <Typography
        align="center"
        variant="subtitle2"
        color={theme.palette.text.secondary}
      >
        Viseron
      </Typography>
      <Typography align="center" variant="subtitle2">
        <Link
          target="_blank"
          href="https://github.com/roflcoopter/viseron"
          color={theme.palette.text.secondary}
        >
          <GitHubIcon
            fontSize="small"
            sx={{
              verticalAlign: "middle",
              marginTop: "-3px",
              marginRight: "5px",
            }}
          />
          GitHub
        </Link>
      </Typography>
    </Footer>
  );
}
