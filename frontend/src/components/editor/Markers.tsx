import Box from "@mui/material/Box";
import List from "@mui/material/List";
import ListItem, { listItemClasses } from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api.js";

interface MarkersProps {
  editor: monaco.editor.IStandaloneCodeEditor | undefined;
  markers: monaco.editor.IMarker[];
  width: number | string;
}

const markerName = {
  1: "hint",
  2: "info",
  4: "warning",
  8: "error",
};

const markerColors = {
  1: "green",
  2: "green",
  4: "yellow",
  8: "red",
};

function Markers({ editor, markers, width }: MarkersProps) {
  if (markers.length === 0) {
    return null;
  }

  return (
    <Box
      sx={{
        minHeight: "10vh",
        maxHeight: "10vh",
        overflow: "auto",
        width,
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
        {markers.map((marker, index) => (
          <ListItem
            // eslint-disable-next-line react/no-array-index-key
            key={index}
            dense
            disablePadding
            onClick={() => {
              if (editor) {
                editor.setPosition({
                  lineNumber: marker.startLineNumber,
                  column: marker.startColumn,
                });
                editor.revealLineInCenter(marker.startLineNumber);
                editor.focus();
              }
            }}
          >
            <Box
              className={`codicon codicon-${markerName[marker.severity]}`}
              component="div"
              sx={{
                color: markerColors[marker.severity],
                display: "inline",
                paddingLeft: "5px",
                paddingRight: "5px",
              }}
            />
            <ListItemText
              primary={marker.message}
              primaryTypographyProps={{
                display: "inline",
              }}
              secondary={` [${marker.startLineNumber}, ${marker.startColumn}]`}
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
}

export default Markers;
