import Container from "@mui/material/Container";
import { lazy } from "react";

import { useHideScrollbar } from "hooks/UseHideScrollbar";
import { useTitle } from "hooks/UseTitle";

const Editor = lazy(() => import("components/editor/Editor"));
function Configuration() {
  useTitle("Configuration");
  useHideScrollbar();

  return (
    <Container maxWidth={false} sx={{ paddingX: 2}}>
      <Editor />
    </Container>
  );
}

export default Configuration;
