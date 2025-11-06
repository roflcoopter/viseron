import { Add, Template, SubtractAlt } from "@carbon/icons-react";
import SpeedDial from "@mui/material/SpeedDial";
import SpeedDialAction from "@mui/material/SpeedDialAction";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import { useState } from "react";

import { SaveViewDialog } from "components/player/view/SaveViewDialog";
import { useGridLayoutStore } from "stores/GridLayoutStore";
import { useViewStore } from "stores/ViewStore";
import { useCameraStore } from "components/camera/useCameraStore";

interface ViewSpeedDialProps {
  /** Position from bottom in pixels */
  bottom?: number;
  /** Position from right in pixels */
  right?: number;
  /** Render inline (no fixed positioning) so it can sit next to other FABs */
  inline?: boolean;
  /** Size of the SpeedDial FAB */
  size?: 'small' | 'medium' | 'large';
}

export function ViewSpeedDial({ bottom = 16, right = 16, inline = false, size = 'medium' }: ViewSpeedDialProps) {
  const [open, setOpen] = useState(false);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [contextMenu, setContextMenu] = useState<{
    mouseX: number;
    mouseY: number;
    viewId: string;
    viewName: string;
  } | null>(null);
  
  const { views, removeView } = useViewStore();
  const { setCurrentLayout, setLayoutConfig } = useGridLayoutStore();
  const { setSelectedCameras, setSelectionOrder } = useCameraStore();

  const handleLoadView = (viewId: string) => {
    const view = views.find(v => v.id === viewId);
    if (view) {
      // Load layout configuration
      setCurrentLayout(view.layoutType);
      setLayoutConfig(view.layoutConfig);
      
      // Load camera selection and order
      setSelectedCameras(view.selectedCameras);
      setSelectionOrder(view.selectionOrder);
    }
    setOpen(false);
  };

  const handleSaveView = () => {
    setSaveDialogOpen(true);
    setOpen(false);
  };

  const handleViewRightClick = (event: React.MouseEvent, viewId: string, viewName: string) => {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({
      mouseX: event.clientX - 2,
      mouseY: event.clientY - 4,
      viewId,
      viewName,
    });
  };

  const handleCloseContextMenu = () => {
    setContextMenu(null);
  };

  const handleDeleteView = () => {
    if (contextMenu) {
      removeView(contextMenu.viewId);
    }
    handleCloseContextMenu();
  };

  return (
    <>
       <SpeedDial
         ariaLabel="View SpeedDial"
         sx={inline ? { ml: 0 } : { position: 'fixed', bottom, right, zIndex: 1000 }}
         icon={<Template size={size === 'small' ? 20 : 24} />}
         onClose={() => setOpen(false)}
         onOpen={() => setOpen(true)}
         open={open}
         direction="up"
         FabProps={{
           size
         }}
       >
        {/* Add new view action */}
        {views.length < 5 && (
          <SpeedDialAction
            key="add-view"
            icon={<Add size={20} />}
            tooltipTitle="Save Current View"
            onClick={handleSaveView}
            FabProps={{
              size: "small",
              color: "primary"
            }}
          />
        )}
        
        {/* Load saved views actions */}
        {views.map((view, index) => (
          <SpeedDialAction
            key={view.id}
            icon={<span style={{ fontWeight: 'bold', fontSize: '14px' }}>{index + 1}</span>}
            tooltipTitle={`Load ${view.name}`}
            onClick={() => handleLoadView(view.id)}
            onContextMenu={(e) => handleViewRightClick(e, view.id, view.name)}
            FabProps={{
              size: "small",
              color: "secondary"
            }}
          />
        ))}
      </SpeedDial>

      <Menu
        open={contextMenu !== null}
        onClose={handleCloseContextMenu}
        anchorReference="anchorPosition"
        anchorPosition={
          contextMenu !== null
            ? { top: contextMenu.mouseY, left: contextMenu.mouseX }
            : undefined
        }
      >
        <MenuItem onClick={handleDeleteView}>
          <ListItemIcon>
            <SubtractAlt size={16} />
          </ListItemIcon>
          <ListItemText>Delete {contextMenu?.viewName}</ListItemText>
        </MenuItem>
      </Menu>

      <SaveViewDialog 
        open={saveDialogOpen}
        onClose={() => setSaveDialogOpen(false)}
      />
    </>
  );
}