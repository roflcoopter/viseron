import { Renew, Restart, Save } from "@carbon/icons-react";
import Editor, { Monaco, loader } from "@monaco-editor/react";
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
import SetupErrorsSidebar from "components/editor/SetupErrorsSidebar";
import { Loading } from "components/loading/Loading";
import { ViseronContext } from "context/ViseronContext";
import { useResizeObserver } from "hooks/UseResizeObserver";
import {
  getConfig,
  reloadConfig,
  restartViseron,
  saveConfig,
} from "lib/commands";

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

const editorWidth = "100%";

function ConfigEditor() {
  const viseron = useContext(ViseronContext);
  const theme = useTheme();

  const editorInstance = useRef<monaco.editor.IStandaloneCodeEditor>(undefined);
  const markersRef = useRef<monaco.editor.IMarker[]>([]);
  const editorContainerRef = useRef<HTMLDivElement>(null);

  const handleEditorContainerResize = useCallback<ResizeObserverCallback>(
    (entries) => {
      if (editorInstance.current && entries.length > 0) {
        const { width, height } = entries[0].contentRect;
        editorInstance.current.layout({ width, height });
      }
    },
    [],
  );

  useResizeObserver(editorContainerRef, handleEditorContainerResize);

  const [configUnsaved, setConfigUnsaved] = useState<boolean>(false);
  const [savedConfig, setSavedConfig] = useState<string | undefined>(undefined);
  const [markers, setMarkers] = useState<monaco.editor.IMarker[]>([]);
  const [savePending, setSavePending] = useState(false);
  const [errorDialog, setErrorDialog] = useState({ open: false, text: "" });
  const [syntaxWarningDialog, setSyntaxWarningDialog] = useState(false);

  const [restartPending, setRestartPending] = useState(false);
  const [restartDialog, setRestartDialog] = useState({ open: false, text: "" });

  const [reloadPending, setReloadPending] = useState(false);
  const [reloadResultDialog, setReloadResultDialog] = useState<{
    open: boolean;
    title: string;
    text: string;
  }>({
    open: false,
    title: "",
    text: "",
  });

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

  const handleReloadConfig = () => {
    if (viseron.connection) {
      setReloadPending(true);
      reloadConfig(viseron.connection).then(
        (result) => {
          setReloadPending(false);
          if (!result.success) {
            setReloadResultDialog({
              open: true,
              title: "Reload failed",
              text: "Configuration validation failed. Check the setup errors panel for details.",
            });
          } else if (result.restart_required) {
            setReloadResultDialog({
              open: true,
              title: "Reload completed",
              text: "Configuration was reloaded, but some changes require a restart to take effect.",
            });
          }
          editorInstance.current?.focus();
        },
        (reason) => {
          setReloadPending(false);
          setReloadResultDialog({
            open: true,
            title: "Reload failed",
            text: reason.message,
          });
        },
      );
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

  const onValidate = (currentMarkers: monaco.editor.IMarker[]) => {
    setMarkers(currentMarkers);
    markersRef.current = currentMarkers;
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
    <div style={{ height: "100%" }}>
      <Dialog
        open={errorDialog.open}
        onClose={() => {
          setErrorDialog({ open: false, text: "" });
        }}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">
          An error occurred when saving configuration.
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
        <DialogTitle id="alert-dialog-title">Syntax errors.</DialogTitle>
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
        <DialogTitle id="alert-dialog-title">Restart Viseron.</DialogTitle>
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
      <Dialog
        open={reloadResultDialog.open}
        onClose={() => {
          setReloadResultDialog({ ...reloadResultDialog, open: false });
          // Editor does not focus without the timer
          setTimeout(() => {
            editorInstance.current?.focus();
          }, 1);
        }}
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <DialogTitle id="alert-dialog-title">
          {reloadResultDialog.title}
        </DialogTitle>
        <DialogContent>
          <DialogContentText component="div" id="alert-dialog-description">
            {reloadResultDialog.text}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setReloadResultDialog({ ...reloadResultDialog, open: false });
              // Editor does not focus without the timer
              setTimeout(() => {
                editorInstance.current?.focus();
              }, 1);
            }}
          >
            OK
          </Button>
        </DialogActions>
      </Dialog>
      <Stack
        justifyContent="flex-start"
        alignItems="flex-start"
        paddingTop={1}
        spacing={2}
        height="100%"
      >
        <Stack
          direction="row"
          justifyContent="flex-start"
          alignItems="flex-start"
          spacing={2}
        >
          <span>
            <Button
              startIcon={<Restart />}
              loadingPosition="start"
              onClick={handleRestart}
              variant="contained"
              loading={restartPending}
              color="error"
            >
              Restart
            </Button>
          </span>
          <span>
            <Button
              startIcon={<Renew />}
              loadingPosition="start"
              onClick={handleReloadConfig}
              variant="contained"
              loading={reloadPending}
            >
              Reload
            </Button>
          </span>
          <Tooltip title="Ctrl+S" enterDelay={300}>
            <span>
              <Button
                startIcon={<Save />}
                loadingPosition="start"
                onClick={handleSave}
                variant="contained"
                loading={savePending}
                disabled={!configUnsaved}
              >
                Save
              </Button>
            </span>
          </Tooltip>
        </Stack>
        <Box
          sx={{
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            gap: 1,
            width: "100%",
            flex: 1,
            minHeight: 0,
            overflow: "hidden",
          }}
        >
          <Box
            sx={{
              position: "relative",
              flex: 1,
              minHeight: 0,
              minWidth: 0,
              overflow: "hidden",
            }}
          >
            <Backdrop
              open={savePending}
              sx={{ position: "absolute", zIndex: 1 }}
            >
              <CircularProgress enableTrackSlot color="inherit" />
            </Backdrop>
            <Card
              variant="outlined"
              sx={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                backgroundColor: "#fffffe",
                ...theme.applyStyles("dark", {
                  backgroundColor: "#1e1e1e",
                }),
              }}
            >
              <Box ref={editorContainerRef} sx={{ flex: 1, minHeight: 0 }}>
                <Editor
                  height="100%"
                  defaultLanguage="yaml"
                  theme={`${theme.palette.mode === "dark" ? "vs-dark" : "light"}`}
                  defaultValue={savedConfig}
                  options={options}
                  onChange={onChange}
                  onMount={onMount}
                  onValidate={onValidate}
                />
              </Box>
              {markers.length > 0 && <Divider />}
              <Markers
                editor={editorInstance.current}
                markers={markers}
                width={editorWidth}
              />
            </Card>
          </Box>
          <Box
            sx={{
              width: { xs: "100%", md: "340px" },
              maxHeight: { xs: "30vh", md: "100%" },
              flexShrink: { xs: 1, md: 0 },
              minHeight: 0,
              overflow: "hidden",
            }}
          >
            <SetupErrorsSidebar />
          </Box>
        </Box>
      </Stack>
    </div>
  );
}

export default ConfigEditor;
