import Editor, { Monaco, loader } from "@monaco-editor/react";
import { RestartAlt } from "@mui/icons-material";
import SaveIcon from "@mui/icons-material/Save";
import LoadingButton from "@mui/lab/LoadingButton";
import Backdrop from "@mui/material/Backdrop";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import { useTheme } from "@mui/material/styles";
import * as monaco from "monaco-editor";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import { configureMonacoYaml } from "monaco-yaml";
import { useCallback, useContext, useEffect, useRef, useState } from "react";

import Markers from "components/editor/Markers";
import { Loading } from "components/loading/Loading";
import { ViseronContext } from "context/ViseronContext";
import { getConfig, restartViseron, saveConfig } from "lib/commands";

import YamlWorker from "./yaml.worker.js?worker";

type GlobalThis = typeof globalThis &
  Window & {
    MonacoEnvironment: any;
  };

(window as GlobalThis).MonacoEnvironment = {
  getWorker(_: any, label: string) {
    if (label === "yaml") {
      return new YamlWorker();
    }
    return new EditorWorker();
  },
};

loader.config({ monaco });
loader.init().then();

configureMonacoYaml(monaco, {
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

const editorWidth = "80vw";

const useResize = (
  editorRef: React.MutableRefObject<
    monaco.editor.IStandaloneCodeEditor | undefined
  >,
) => {
  const updateDimensions = useCallback(() => {
    if (editorRef.current) {
      editorRef.current.layout();
    }
  }, [editorRef]);

  useEffect(() => {
    window.addEventListener("resize", updateDimensions, true);
    return () => {
      window.removeEventListener("resize", updateDimensions, true);
    };
  }, [updateDimensions]);
};

const ConfigEditor = () => {
  const viseron = useContext(ViseronContext);
  const theme = useTheme();

  const editorInstance = useRef<monaco.editor.IStandaloneCodeEditor>();
  const markersRef = useRef<monaco.editor.IMarker[]>([]);

  useResize(editorInstance);

  const [configUnsaved, setConfigUnsaved] = useState<boolean>(false);
  const [savedConfig, setSavedConfig] = useState<string | undefined>(undefined);
  const [markers, setMarkers] = useState<monaco.editor.IMarker[]>([]);
  const [savePending, setSavePending] = useState(false);
  const [errorDialog, setErrorDialog] = useState({ open: false, text: "" });
  const [syntaxWarningDialog, setSyntaxWarningDialog] = useState(false);

  const [restartPending, setRestartPending] = useState(false);
  const [restartDialog, setRestartDialog] = useState({ open: false, text: "" });

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
      },
    );
  };

  const handleSave = () => {
    if (viseron.connection && editorInstance.current) {
      if (markersRef.current.length > 0) {
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
        setRestartPending(false),
      );
    };
    _restart();
  };

  const handleRestart = () => {
    if (viseron.connection && editorInstance.current) {
      let text = "Are you sure you want to restart Viseron?";
      if (markersRef.current.length > 0) {
        text = `You have synxat errors in your config. ${text}`;
      } else if (configUnsaved) {
        text = `You have unsaved changes to your config. Do you want to restart Viseron anyway?`;
      }
      setRestartDialog({ open: true, text });
    }
  };

  const onMount = (
    editor: monaco.editor.IStandaloneCodeEditor,
    _monaco: Monaco,
  ) => {
    editorInstance.current = editor;
    editor.focus();
    editor.addCommand(
      // eslint-disable-next-line no-bitwise
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
      () => {
        handleSave();
      },
    );
  };

  const onChange = (
    editorContents: string | undefined,
    _event: monaco.editor.IModelContentChangedEvent,
  ) => {
    if (editorContents === savedConfig) {
      setConfigUnsaved(false);
      return;
    }

    if (configUnsaved === false) {
      setConfigUnsaved(true);
    }
  };

  function onValidate(currentMarkers: monaco.editor.IMarker[]) {
    setMarkers(currentMarkers);
    markersRef.current = currentMarkers;
  }

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
            height: markers.length > 0 ? "80vh" : "90vh",
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
            <Editor
              height={markers.length > 0 ? "80vh" : "90vh"}
              defaultLanguage="yaml"
              theme={`${theme.palette.mode === "dark" ? "vs-dark" : "light"}`}
              defaultValue={savedConfig}
              options={options}
              onChange={onChange}
              onMount={onMount}
              onValidate={onValidate}
            />
            {markers.length > 0 && <Divider />}
            <Markers
              editor={editorInstance.current}
              markers={markers}
              width={editorWidth}
            />
          </Card>
        </Box>
      </Stack>
    </div>
  );
};

export default ConfigEditor;
