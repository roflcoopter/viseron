import { RestartAlt } from "@mui/icons-material";
import SaveIcon from "@mui/icons-material/Save";
import LoadingButton from "@mui/lab/LoadingButton";
import {
  Box,
  DialogTitle,
  List,
  ListItem,
  ListItemText,
  listItemClasses,
} from "@mui/material";
import Backdrop from "@mui/material/Backdrop";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import { useTheme } from "@mui/material/styles";
import "monaco-editor";
import * as monacoEditor from "monaco-editor/esm/vs/editor/editor.api";
import { setDiagnosticsOptions } from "monaco-yaml";
import { useCallback, useContext, useEffect, useRef, useState } from "react";
import MonacoEditor, {
  ChangeHandler,
  EditorDidMount,
  EditorWillUnmount,
} from "react-monaco-editor";

import { Loading } from "components/loading/Loading";
import { ViseronContext } from "context/ViseronContext";
import { getConfig, restartViseron, saveConfig } from "lib/commands";

type GlobalThis = typeof globalThis &
  Window & {
    MonacoEnvironment: any;
  };

(window as GlobalThis).MonacoEnvironment = {
  getWorker(_moduleId: any, label: string) {
    switch (label) {
      case "editorWorkerService":
        return new Worker(
          new URL("monaco-editor/esm/vs/editor/editor.worker", import.meta.url)
        );
      case "yaml":
        return new Worker(new URL("monaco-yaml/yaml.worker", import.meta.url));
      default:
        throw new Error(`Unknown label ${label}`);
    }
  },
};

setDiagnosticsOptions({
  enableSchemaRequest: true,
  hover: true,
  completion: true,
  validate: true,
  format: true,
  customTags: ["!secret"],
});

const renderWhitespace:
  | "all"
  | "none"
  | "boundary"
  | "selection"
  | "trailing"
  | undefined = "all";

const options = {
  selectOnLineNumbers: true,
  scrollBeyondLastLine: false,
  renderWhitespace,
  renderIndentGuides: true,
};

interface ProblemsProps {
  editor: monacoEditor.editor.IStandaloneCodeEditor | undefined;
  problems: monacoEditor.editor.IMarker[];
}

const problemName = {
  1: "hint",
  2: "info",
  4: "warning",
  8: "error",
};

const problemColors = {
  1: "green",
  2: "green",
  4: "yellow",
  8: "red",
};

const editorWidth = "80vw";

const Problems = ({ editor, problems }: ProblemsProps) => {
  if (problems.length === 0) {
    return null;
  }

  return (
    <Box
      sx={{
        minHeight: "10vh",
        maxHeight: "10vh",
        overflow: "auto",
        width: editorWidth,
      }}
    >
      <List
        sx={{
          [`& .active, & .${listItemClasses.root}:hover`]: {
            backgroundColor: "rgba(100, 100, 100, 0.7)",
            cursor: "pointer",
          },
        }}
      >
        {problems.map((problem, index) => (
          <ListItem
            key={index}
            dense={true}
            disablePadding={true}
            onClick={() => {
              if (editor) {
                editor.setPosition({
                  lineNumber: problem.startLineNumber,
                  column: problem.startColumn,
                });
                editor.revealLineInCenter(problem.startLineNumber);
                editor.focus();
              }
            }}
          >
            <Box
              className={`codicon codicon-${problemName[problem.severity]}`}
              component="div"
              sx={{
                color: problemColors[problem.severity],
                display: "inline",
                paddingLeft: "5px",
                paddingRight: "5px",
              }}
            />
            <ListItemText
              primary={problem.message}
              primaryTypographyProps={{
                display: "inline",
              }}
              secondary={` [${problem.startLineNumber}, ${problem.startColumn}]`}
              secondaryTypographyProps={{
                display: "inline",
              }}
              sx={{ marginTop: 0, marginBottom: 0 }}
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );
};

const Editor = () => {
  const viseron = useContext(ViseronContext);

  const theme = useTheme();

  const editorInstance = useRef<monacoEditor.editor.IStandaloneCodeEditor>();
  const monacoInstance = useRef<typeof monacoEditor>();
  const problemsRef = useRef<monacoEditor.editor.IMarker[]>([]);

  const [configUnsaved, setConfigUnsaved] = useState<boolean>(false);
  const [savedConfig, setSavedConfig] = useState<string | undefined>(undefined);
  const [problems, setProblems] = useState<monacoEditor.editor.IMarker[]>([]);
  const [savePending, setSavePending] = useState(false);
  const [errorDialog, setErrorDialog] = useState({ open: false, text: "" });
  const [syntaxWarningDialog, setSyntaxWarningDialog] = useState(false);

  const [restartPending, setRestartPending] = useState(false);
  const [restartDialog, setRestartDialog] = useState({ open: false, text: "" });

  const updateDimensions = useCallback(() => {
    if (editorInstance) {
      editorInstance!.current!.layout();
    }
  }, [editorInstance]);

  const onChange: ChangeHandler = (editorContents, _event) => {
    if (editorContents === savedConfig) {
      setConfigUnsaved(false);
      return;
    }

    if (configUnsaved === false) {
      setConfigUnsaved(true);
    }
  };

  const save = () => {
    setSavePending(true);
    const config = editorInstance!.current!.getModel()!.getValue();
    saveConfig(viseron.connection!, config).then(
      (_value) => {
        setSavePending(false);
        setSavedConfig(config);
        setConfigUnsaved(false);
        editorInstance.current?.focus();
      },
      (reason) => {
        setSavePending(false);
        setErrorDialog({ open: true, text: reason.message });
      }
    );
  };

  const handleSave = () => {
    if (viseron.connection && editorInstance.current) {
      if (problemsRef.current.length > 0) {
        setSyntaxWarningDialog(true);
        return;
      }
      save();
    }
  };

  const _restartViseron = () => {
    const _restart = async () => {
      setRestartPending(true);
      await restartViseron(viseron.connection!).catch(() =>
        setRestartPending(false)
      );
    };
    _restart();
  };

  const handleRestart = () => {
    if (viseron.connection && editorInstance.current) {
      let text = "Are you sure you want to restart Viseron?";
      if (problemsRef.current.length > 0) {
        text = `You have synxat errors in your config. ${text}`;
      } else if (configUnsaved) {
        text = `You have unsaved changes to your config. Do you want to restart Viseron anyway?`;
      }
      setRestartDialog({ open: true, text });
    }
  };

  const editorDidMount: EditorDidMount = (editor, monaco) => {
    editorInstance.current = editor;
    monacoInstance.current = monaco;

    editor.focus();
    window.addEventListener("resize", updateDimensions, true);
    monaco.editor.onDidChangeMarkers(([resource]) => {
      const markers = monaco.editor.getModelMarkers({ resource });
      setProblems(markers);
      problemsRef.current = markers;
    });
    editorInstance!.current!.addCommand(
      // eslint-disable-next-line no-bitwise
      monacoEditor.KeyMod.CtrlCmd | monacoEditor.KeyCode.KeyS,
      () => {
        handleSave();
      }
    );
  };

  const editorWillUnmount: EditorWillUnmount = (_editor, _monaco) => {
    window.removeEventListener("resize", updateDimensions, true);
  };

  useEffect(() => {
    if (viseron.connection) {
      const _getConfig = async () => {
        const config = await getConfig(viseron.connection!);
        setSavedConfig(config);
      };
      _getConfig();
    }
  }, [viseron.connection]);

  useEffect(() => {
    setRestartPending(!viseron.connected);
  }, [viseron.connected]);

  if (savedConfig === undefined) {
    return <Loading text="Loading Configuration" />;
  }

  return (
    <div>
      <Dialog
        open={errorDialog.open}
        onClose={() => {
          setErrorDialog({ open: false, text: "" });
        }}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">
          {"An error occurred when saving configuration."}
        </DialogTitle>
        <DialogContent>
          <DialogContentText id="alert-dialog-description">
            {errorDialog.text}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setErrorDialog({ open: false, text: "" });
            }}
          >
            OK
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={syntaxWarningDialog}
        onClose={() => {
          setSyntaxWarningDialog(false);
          // Editor does not focus without the timer
          setTimeout(() => {
            editorInstance.current?.focus();
          }, 1);
        }}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">{"Syntax errors."}</DialogTitle>
        <DialogContent>
          <DialogContentText id="alert-dialog-description">
            You have syntax errors in your config. Are you sure you want to
            save?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setSyntaxWarningDialog(false);
              save();
            }}
          >
            Yes
          </Button>
          <Button
            onClick={() => {
              setSyntaxWarningDialog(false);
              // Editor does not focus without the timer
              setTimeout(() => {
                editorInstance.current?.focus();
              }, 1);
            }}
          >
            Cancel
          </Button>
        </DialogActions>
      </Dialog>
      <Dialog
        open={restartDialog.open}
        onClose={() => {
          setRestartDialog({ ...restartDialog, open: false });
        }}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">{"Restart Viseron."}</DialogTitle>
        {restartDialog.text && (
          <DialogContent>
            <DialogContentText id="alert-dialog-description">
              {restartDialog.text}
            </DialogContentText>
          </DialogContent>
        )}
        <DialogActions>
          <Button
            onClick={() => {
              _restartViseron();
              setRestartDialog({ ...restartDialog, open: false });
              // Editor does not focus without the timer
              setTimeout(() => {
                editorInstance.current?.focus();
              }, 1);
            }}
          >
            Yes
          </Button>
          <Button
            onClick={() => {
              setRestartDialog({ ...restartDialog, open: false });
              // Editor does not focus without the timer
              setTimeout(() => {
                editorInstance.current?.focus();
              }, 1);
            }}
          >
            Cancel
          </Button>
        </DialogActions>
      </Dialog>
      <Stack justifyContent="flex-start" alignItems="flex-start" spacing={2}>
        <Stack
          direction="row"
          justifyContent="flex-start"
          alignItems="flex-start"
          spacing={2}
        >
          <Tooltip title="Ctrl+S" enterDelay={300}>
            <span>
              <LoadingButton
                startIcon={<SaveIcon />}
                loadingPosition="start"
                onClick={handleSave}
                variant="contained"
                loading={savePending}
                disabled={!configUnsaved}
              >
                Save
              </LoadingButton>
            </span>
          </Tooltip>
          <span>
            <LoadingButton
              startIcon={<RestartAlt />}
              loadingPosition="start"
              onClick={handleRestart}
              variant="contained"
              loading={restartPending}
              color="error"
            >
              Restart
            </LoadingButton>
          </span>
        </Stack>
        <Box
          sx={{
            width: editorWidth,
            height: problems.length > 0 ? "80vh" : "90vh",
            position: "relative",
          }}
        >
          <Backdrop open={savePending} sx={{ position: "absolute", zIndex: 1 }}>
            <CircularProgress color="inherit" />
          </Backdrop>
          <Card
            variant="outlined"
            sx={{
              backgroundColor:
                theme.palette.mode === "dark" ? "#1e1e1e" : "#fffffe",
            }}
          >
            <MonacoEditor
              width="editorWidth"
              height={problems.length > 0 ? "80vh" : "90vh"}
              language="yaml"
              theme={`${theme.palette.mode === "dark" ? "vs-dark" : "light"}`}
              defaultValue={savedConfig}
              options={options}
              onChange={onChange}
              editorDidMount={editorDidMount}
              editorWillUnmount={editorWillUnmount}
            />
            {problems.length > 0 && <Divider />}
            <Problems editor={editorInstance.current} problems={problems} />
          </Card>
        </Box>
      </Stack>
    </div>
  );
};

export default Editor;
