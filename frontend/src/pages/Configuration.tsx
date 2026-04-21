import Container from "@mui/material/Container";
import { useTheme } from "@mui/material/styles";
import { lazy } from "react";

import { useHideScrollbar } from "hooks/UseHideScrollbar";
import { useTitle } from "hooks/UseTitle";

const Editor = lazy(() => import("components/editor/Editor"));
function Configuration() {
  useTitle("Configuration");
  useHideScrollbar();
  const theme = useTheme();

  return (
    <Container
      maxWidth={false}
      sx={{
        paddingX: { xs: 1, md: 2 },
        height: `calc(99dvh - var(--header-height, ${theme.headerHeight}px) - ${theme.headerMargin})`,
      }}
    >
      <Editor />
    </Container>
  );
}

export default Configuration;
