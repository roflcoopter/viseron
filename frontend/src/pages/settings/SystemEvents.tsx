import { Erase, PlayFilledAlt, StopFilledAlt } from "@carbon/icons-react";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import yaml from "js-yaml";
import { useContext, useRef, useState } from "react";

import { ViseronContext } from "context/ViseronContext";
import { useToast } from "hooks/UseToast";
import { useSystemDispatchedEvents } from "lib/api/system";
import { subscribeEvent } from "lib/commands";

function SystemEvents() {
  const { connection } = useContext(ViseronContext);
  const toast = useToast();

  const systemDispatchedEvents = useSystemDispatchedEvents({
    refetchInterval: 10000,
  });

  const [event, setEvent] = useState("");
  const [subscribed, setSubscribed] = useState(false);
  const [receivedEvents, setReceivedEvents] = useState<any[]>([]);
  const unsubscribeRef = useRef<null | (() => Promise<void>)>(null);

  const handleSubscribe = async () => {
    if (!connection) {
      return;
    }
    try {
      const unsub = await subscribeEvent<any>(connection, event, (msg) => {
        setReceivedEvents((prev) => [msg, ...prev]);
      });
      unsubscribeRef.current = unsub;
      setSubscribed(true);
    } catch (e: any) {
      setSubscribed(false);
      toast.error(
        `Failed to subscribe to event: ${e?.message || "Unknown error"}`,
      );
    }
  };

  const handleUnsubscribe = async () => {
    if (unsubscribeRef.current) {
      await unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
    setSubscribed(false);
  };

  const handleClearEvents = () => {
    setReceivedEvents([]);
  };

  return (
    <Container sx={{ paddingX: 2 }}>
      <Paper variant="outlined" sx={{ p: 3, mb: 1 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Listen to events
        </Typography>
        <Autocomplete
          disabled={subscribed}
          freeSolo
          forcePopupIcon
          options={systemDispatchedEvents.data?.events || []}
          loading={systemDispatchedEvents.isLoading}
          loadingText="Loading events..."
          onChange={(e, value) => {
            setEvent(value || "");
          }}
          renderInput={(params) => (
            <TextField
              label={subscribed ? "Listening to" : "Event to subscribe to"}
              value={event}
              onChange={(e) => setEvent(e.target.value)}
              {...params}
            />
          )}
          sx={{ mb: 2 }}
        />
        <Box sx={{ display: "flex", gap: 2, mb: 2 }}>
          {subscribed ? (
            <Button
              variant="contained"
              color="warning"
              onClick={handleUnsubscribe}
              startIcon={<StopFilledAlt size={16} />}
            >
              STOP LISTENING
            </Button>
          ) : (
            <Button
              variant="contained"
              onClick={handleSubscribe}
              disabled={!event}
              startIcon={<PlayFilledAlt size={16} />}
            >
              START LISTENING
            </Button>
          )}
          <Button
            variant="contained"
            color="error"
            onClick={handleClearEvents}
            startIcon={<Erase size={16} />}
          >
            CLEAR EVENTS
          </Button>
        </Box>
        <Typography variant="subtitle2">
          When clicking the text field above, you can see a list of all events
          fired since the last restart of Viseron.
        </Typography>
        <Typography variant="subtitle2">
          A star (*) can be used as a wildcard in the event name.
        </Typography>
      </Paper>

      {receivedEvents.length > 0 && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          {receivedEvents.map((ev, idx) => (
            // eslint-disable-next-line react/no-array-index-key
            <Box key={idx} sx={{ mb: 3 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                Event {receivedEvents.length - idx - 1}:
              </Typography>
              <Box
                component="pre"
                sx={{
                  background: "#18181c",
                  color: "#fff",
                  p: 2,
                  borderRadius: 1,
                  fontSize: 14,
                  overflowX: "auto",
                }}
              >
                {yaml.dump(ev)}
              </Box>
            </Box>
          ))}
        </Paper>
      )}
    </Container>
  );
}

export default SystemEvents;
