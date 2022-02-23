import Container from "@mui/material/Container";
import "monaco-editor";

import Editor from "components/editor/Editor";
import { useTitle } from "hooks/UseTitle";

const Configuration = () => {
  useTitle("Configuration");

  return (
    <Container maxWidth={false}>
      <Editor />
    </Container>
  );
};

export default Configuration;
