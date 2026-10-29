import { Edit, RequestQuote, TagEdit, TrashCan } from "@carbon/icons-react";
import { ListItemIcon, ListItemText, Menu, MenuItem } from "@mui/material";

interface ContextMenuState {
  mouseX: number;
  mouseY: number;
  type: "label" | "zone" | "mask" | "osd" | "video_transform";
  index: number;
}

interface ConfigPanelContextMenuProps {
  contextMenu: ContextMenuState | null;
  onClose: () => void;
  onEditZoneName: (index: number) => void;
  onEditZoneLabels: (index: number) => void;
  onEditOSDText: (index: number) => void;
  onEditVideoTransform: (index: number) => void;
  onDelete: () => void;
}

export function ConfigPanelContextMenu({
  contextMenu,
  onClose,
  onEditZoneName,
  onEditZoneLabels,
  onEditOSDText,
  onEditVideoTransform,
  onDelete,
}: ConfigPanelContextMenuProps) {
  return (
    <Menu
      open={contextMenu !== null}
      onClose={onClose}
      anchorReference="anchorPosition"
      anchorPosition={
        contextMenu !== null
          ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
          : undefined
      }
    >
      {contextMenu?.type === "zone" && (
        <>
          <MenuItem
            onClick={() => {
              if (contextMenu) {
                onEditZoneName(contextMenu.index);
              }
              onClose();
            }}
          >
            <ListItemIcon>
              <RequestQuote />
            </ListItemIcon>
            <ListItemText>Edit Name</ListItemText>
          </MenuItem>
          <MenuItem
            onClick={() => {
              if (contextMenu) {
                onEditZoneLabels(contextMenu.index);
              }
              onClose();
            }}
          >
            <ListItemIcon>
              <TagEdit />
            </ListItemIcon>
            <ListItemText>Manage Labels</ListItemText>
          </MenuItem>
        </>
      )}
      {contextMenu?.type === "osd" && (
        <MenuItem
          onClick={() => {
            if (contextMenu) {
              onEditOSDText(contextMenu.index);
            }
            onClose();
          }}
        >
          <ListItemIcon>
            <Edit />
          </ListItemIcon>
          <ListItemText>Edit OSD Text</ListItemText>
        </MenuItem>
      )}
      {contextMenu?.type === "video_transform" && (
        <MenuItem
          onClick={() => {
            if (contextMenu) {
              onEditVideoTransform(contextMenu.index);
            }
            onClose();
          }}
        >
          <ListItemIcon>
            <Edit />
          </ListItemIcon>
          <ListItemText>Edit Transform</ListItemText>
        </MenuItem>
      )}
      <MenuItem onClick={onDelete} sx={{ color: "error.main" }}>
        <ListItemIcon sx={{ color: "error.main" }}>
          <TrashCan />
        </ListItemIcon>
        <ListItemText>Delete</ListItemText>
      </MenuItem>
    </Menu>
  );
}
