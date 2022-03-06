import Container from "@mui/material/Container";
import "monaco-editor";
import { lazy } from "react";

import { useTitle } from "hooks/UseTitle";

const Editor = lazy(() => import("components/editor/Editor"));
const Configuration = () => {
  useTitle("Configuration");

  return (
    <Container maxWidth={false}>
      <Editor />
    </Container>
  );
};

export default Configuration;
