import { Warning } from "@carbon/icons-react";
import { StreamLanguage } from "@codemirror/language";
import { jinja2 } from "@codemirror/legacy-modes/mode/jinja2";
import { TextField } from "@mui/material";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import CodeMirror, { basicSetup } from "@uiw/react-codemirror";
import { useState } from "react";

import { useDebouncedTemplateRender } from "hooks/useDebouncedTemplateRender";

const extensions = [
  basicSetup({ lintKeymap: true }),
  StreamLanguage.define(jinja2),
];

const paperStyle = {
  padding: 3,
  marginBottom: { xs: 2, md: 0 },
  flex: 1,
  display: "flex",
  flexDirection: "column",
  maxHeight: "80vh",
  overflow: "auto",
  height: "100%",
};

type EditorProps = {
  template: string;
  setTemplate: (value: string) => void;
  handleRender: () => Promise<void> | void;
  clearTemplate: () => void;
  loading: boolean;
};

function Editor({
  template,
  setTemplate,
  handleRender,
  clearTemplate,
  loading,
}: EditorProps) {
  const theme = useTheme();

  return (
    <Paper variant="outlined" sx={paperStyle}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Template Editor
      </Typography>
      <CodeMirror
        value={template}
        extensions={extensions}
        theme={theme.palette.mode}
        onChange={(value) => setTemplate(value)}
        style={{
          overflow: "auto",
          marginBottom: "16px",
        }}
      />
      <Box sx={{ display: "flex", gap: 2 }}>
        <Button
          variant="contained"
          onClick={handleRender}
          disabled={loading || !template.trim()}
        >
          Render
        </Button>
        <Button
          variant="contained"
          onClick={clearTemplate}
          disabled={!template.trim()}
        >
          Clear Template
        </Button>
      </Box>
    </Paper>
  );
}

type ResultProps = {
  result: string;
  error: string | null;
};

function Result({ result, error }: ResultProps) {
  return (
    <Paper variant="outlined" sx={paperStyle}>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Result
      </Typography>
      {error ? (
        <Alert severity="error" icon={<Warning size={20} />}>
          {error}
        </Alert>
      ) : result ? (
        <TextField
          value={result}
          multiline
          slotProps={{
            input: {
              readOnly: true,
            },
          }}
        >
          {result}
        </TextField>
      ) : null}
    </Paper>
  );
}

function TemplateEditor() {
  const [template, setTemplate] = useState<string>("");

  const { result, error, loading, renderNow, clear } =
    useDebouncedTemplateRender(template, 500);

  const handleRender = async () => {
    await renderNow();
  };

  const clearTemplate = () => {
    setTemplate("");
    clear();
  };

  return (
    <Container sx={{ paddingX: 2 }}>
      <Grid container spacing={1} alignItems="stretch">
        <Grid size={{ xs: 12, md: 6 }}>
          <Editor
            template={template}
            setTemplate={setTemplate}
            handleRender={handleRender}
            clearTemplate={clearTemplate}
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Result result={result} error={error} />
        </Grid>
      </Grid>
    </Container>
  );
}

export default TemplateEditor;
