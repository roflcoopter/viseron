import Container from "@mui/material/Container";
import { lazy } from "react";

import { useHideScrollbar } from "hooks/UseHideScrollbar";
import { useTitle } from "hooks/UseTitle";

const Editor = lazy(() => import("components/editor/Editor"));
const Configuration = () => {
  useTitle("Configuration");
  useHideScrollbar();

  return (
    <Container maxWidth={false}>
      <Editor />
    </Container>
  );
};

export default Configuration;
