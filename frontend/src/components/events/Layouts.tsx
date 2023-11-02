import CalendarMonthIcon from "@mui/icons-material/CalendarMonth";
import FilterAltIcon from "@mui/icons-material/FilterAlt";
import VideocamIcon from "@mui/icons-material/Videocam";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Container from "@mui/material/Container";
import SpeedDial from "@mui/material/SpeedDial";
import SpeedDialAction from "@mui/material/SpeedDialAction";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { Dayjs } from "dayjs";
import { memo, useEffect, useRef, useState } from "react";

import { CameraPickerDialog } from "components/events/CameraPickerDialog";
import { EventDatePickerDialog } from "components/events/EventDatePickerDialog";
import { PlayerCard } from "components/events/EventPlayerCard";
import { EventTable } from "components/events/EventTable";
import { EventsCameraGrid } from "components/events/EventsCameraGrid";
import * as types from "lib/types";

type FiltersProps = {
  cameras: types.Cameras;
  selectedCamera: types.Camera | null;

  date: Dayjs | null;
  setDate: (date: Dayjs | null) => void;

  changeSource: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera
  ) => void;
};

const Filters = memo(
  ({ cameras, selectedCamera, date, setDate, changeSource }: FiltersProps) => {
    const [open, setOpen] = useState(false);
    const [cameraDialogOpen, setCameraDialogOpen] = useState(false);
    const [dateDialogOpen, setDateDialogOpen] = useState(false);
    const theme = useTheme();

    const handleClose = () => {
      setOpen(false);
    };

    const handleClick = () => {
      setOpen(!open);
    };

    return (
      <>
        <CameraPickerDialog
          open={cameraDialogOpen}
          setOpen={setCameraDialogOpen}
          cameras={cameras}
          changeSource={changeSource}
          selectedCamera={selectedCamera}
        />
        <EventDatePickerDialog
          open={dateDialogOpen}
          setOpen={setDateDialogOpen}
          date={date}
          camera={selectedCamera}
          onChange={(value) => {
            setDateDialogOpen(false);
            setDate(value);
          }}
        />
        <SpeedDial
          ariaLabel="Filters"
          sx={{ position: "absolute", bottom: 16, right: 16 }}
          icon={<FilterAltIcon />}
          onClose={handleClose}
          onClick={handleClick}
          open={open}
        >
          <SpeedDialAction
            icon={<VideocamIcon />}
            tooltipTitle={"Select camera"}
            onClick={() => setCameraDialogOpen(true)}
            FabProps={{
              size: "medium",
              sx: { backgroundColor: theme.palette.primary.main },
            }}
          />
          <SpeedDialAction
            icon={<CalendarMonthIcon />}
            tooltipTitle={"Select date"}
            onClick={() => setDateDialogOpen(true)}
            FabProps={{
              size: "medium",
              sx: { backgroundColor: theme.palette.primary.main },
            }}
          />
        </SpeedDial>
      </>
    );
  }
);

type LayoutProps = {
  cameras: types.Cameras;
  selectedCamera: types.Camera | null;
  selectedRecording: types.Recording | null;
  setSelectedRecording: (recording: types.Recording) => void;
  changeSource: (
    ev: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    camera: types.Camera
  ) => void;
  date: Dayjs | null;
  setDate: (date: Dayjs | null) => void;
};

export const Layout = memo(
  ({
    cameras,
    selectedCamera,
    selectedRecording,
    setSelectedRecording,
    changeSource,
    date,
    setDate,
  }: LayoutProps) => {
    const theme = useTheme();

    return (
      <Container style={{ display: "flex" }}>
        <div
          style={{
            width: "100%",
            display: "flex",
            flexDirection: "column",
            marginRight: "10px",
          }}
        >
          <PlayerCard camera={selectedCamera} recording={selectedRecording} />
          <EventsCameraGrid
            cameras={cameras}
            changeSource={changeSource}
            selectedCamera={selectedCamera}
          ></EventsCameraGrid>
        </div>
        <Card
          variant="outlined"
          sx={{
            width: "550px",
            height: `calc(98dvh - ${theme.headerHeight}px)`,
            overflow: "auto",
          }}
        >
          <CardContent sx={{ padding: 0 }}>
            {selectedCamera ? (
              <EventTable
                camera={selectedCamera}
                date={date}
                selectedRecording={selectedRecording}
                setSelectedRecording={setSelectedRecording}
              />
            ) : (
              <Typography align="center" sx={{ marginTop: "20px" }}>
                Select a camera to load events
              </Typography>
            )}
          </CardContent>
        </Card>
        <Filters
          cameras={cameras}
          selectedCamera={selectedCamera}
          date={date}
          setDate={setDate}
          changeSource={changeSource}
        />
      </Container>
    );
  }
);

export const LayoutSmall = memo(
  ({
    cameras,
    selectedCamera,
    selectedRecording,
    setSelectedRecording,
    changeSource,
    date,
    setDate,
  }: LayoutProps) => {
    const theme = useTheme();

    // Observe div height to calculate the height of the EventTable
    const [height, setHeight] = useState();
    const observedDiv: any = useRef<HTMLDivElement>();
    const resizeObserver = useRef<ResizeObserver>();
    useEffect(() => {
      if (observedDiv.current) {
        resizeObserver.current = new ResizeObserver(() => {
          setHeight(observedDiv.current.clientHeight + theme.headerHeight);
        });
        resizeObserver.current.observe(observedDiv.current);
      }
      return () => {
        if (resizeObserver.current) {
          resizeObserver.current.disconnect();
        }
      };
    }, [theme.headerHeight]);

    return (
      <Container maxWidth={false} sx={{ height: "100%" }}>
        <div ref={observedDiv}>
          <PlayerCard camera={selectedCamera} recording={selectedRecording} />
        </div>
        <Card
          variant="outlined"
          sx={{
            width: "100%",
            overflow: "auto",
            height: `calc(97dvh - ${height}px)`,
          }}
        >
          <CardContent sx={{ padding: 0 }}>
            {selectedCamera ? (
              <EventTable
                camera={selectedCamera}
                date={date}
                selectedRecording={selectedRecording}
                setSelectedRecording={setSelectedRecording}
              />
            ) : (
              <Typography align="center" sx={{ marginTop: "20px" }}>
                Select a camera to load events
              </Typography>
            )}
          </CardContent>
        </Card>
        <Filters
          cameras={cameras}
          selectedCamera={selectedCamera}
          date={date}
          setDate={setDate}
          changeSource={changeSource}
        />
      </Container>
    );
  }
);
