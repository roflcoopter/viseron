import Container from "@mui/material/Container";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell, { tableCellClasses } from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { styled, useTheme } from "@mui/material/styles";
import { useContext, useEffect, useState } from "react";

import SearchField from "components/SearchField";
import { ViseronContext } from "context/ViseronContext";
import { useTitle } from "hooks/UseTitle";
import { getEntities, subscribeStates } from "lib/commands";
import * as types from "lib/types";
import { SubscriptionUnsubscribe } from "lib/websockets";

interface Filters {
  entity_id: string;
  state: string;
  attributes: string;
}

const StyledTableCell = styled(TableCell)(() => ({
  [`&.${tableCellClasses.body}`]: {
    fontSize: 14,
    verticalAlign: "top",
    overflowWrap: "anywhere",
  },
}));

const StyledTableRow = styled(TableRow)(({ theme }) => ({
  "&:nth-of-type(odd)": {
    backgroundColor: theme.palette.action.hover,
  },
}));

const calculateEntities = (entities: types.Entities, filters: Filters) =>
  Object.values(entities).filter((entity) => {
    if (filters.entity_id) {
      if (
        !entity.entity_id.toString().toLowerCase().includes(filters.entity_id)
      ) {
        return false;
      }
    }
    if (filters.state) {
      if (!entity.state.toString().toLowerCase().includes(filters.state)) {
        return false;
      }
    }
    if (filters.attributes) {
      for (const [key, attributeValue] of Object.entries(entity.attributes)) {
        if (key.toString().toLowerCase().includes(filters.attributes)) {
          return true;
        }

        if (
          attributeValue &&
          attributeValue.toString().toLowerCase().includes(filters.attributes)
        ) {
          return true;
        }
      }
      // No attribute (key or value) matched the filter
      return false;
    }

    return true;
  });

const Entities = () => {
  useTitle("Entities");
  const viseron = useContext(ViseronContext);
  const theme = useTheme();

  const [entities, setEntities] = useState<types.Entities>({});
  const [filteredEntities, setFilteredEntities] = useState<types.Entity[]>([]);
  const [filters, setFilters] = useState<Filters>({
    entity_id: "",
    state: "",
    attributes: "",
  });

  const handleChange =
    (prop: keyof Filters) => (event: React.ChangeEvent<HTMLInputElement>) => {
      setFilters({ ...filters, [prop]: event.target.value.toLowerCase() });
    };

  useEffect(() => {
    const stateChanged = async (stateChangedEvent: types.StateChangedEvent) => {
      setEntities((prevEntities) => {
        const newEntity: types.Entity = {
          entity_id: stateChangedEvent.data.entity_id,
          state: stateChangedEvent.data.current_state.state,
          attributes: stateChangedEvent.data.current_state.attributes,
        };
        return {
          ...prevEntities,
          [stateChangedEvent.data.entity_id]: newEntity,
        };
      });
    };

    let unsub: SubscriptionUnsubscribe | null = null;
    const subscribeEntities = async () => {
      if (viseron.connection) {
        unsub = await subscribeStates(viseron.connection, stateChanged);
        setEntities(await getEntities(viseron.connection));
      }
    };
    subscribeEntities();
    return () => {
      const unsubscribeEntities = async () => {
        if (viseron.connected && unsub) {
          try {
            await unsub();
          } catch (error) {
            // Connection is probably closed
          }
          unsub = null;
        }
      };
      unsubscribeEntities();
    };
  }, [viseron.connected, viseron.connection]);

  useEffect(() => {
    setFilteredEntities(calculateEntities(entities, filters));
  }, [entities, filters]);

  return (
    <Container maxWidth={false}>
      <TableContainer component={Paper}>
        <Table
          sx={{
            [`& .${tableCellClasses.root}`]: {
              border: `1px solid ${theme.palette.background.default}`,
            },
          }}
          style={{
            tableLayout: "fixed",
          }}
        >
          <TableHead>
            <TableRow>
              <StyledTableCell sx={{ width: "40%" }}>Entity ID</StyledTableCell>
              <StyledTableCell sx={{ width: "15%" }}>State</StyledTableCell>
              <StyledTableCell>Attributes</StyledTableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <StyledTableRow>
              <StyledTableCell sx={{ padding: 0, paddingTop: "5px" }}>
                <SearchField
                  text="Filter entities"
                  onChange={handleChange("entity_id")}
                />
              </StyledTableCell>
              <StyledTableCell sx={{ padding: 0, paddingTop: "5px" }}>
                <SearchField
                  text="Filter states"
                  onChange={handleChange("state")}
                />
              </StyledTableCell>
              <StyledTableCell sx={{ padding: 0, paddingTop: "5px" }}>
                <SearchField
                  text="Filter attributes"
                  onChange={handleChange("attributes")}
                />
              </StyledTableCell>
            </StyledTableRow>
            {filteredEntities.map((entity) => (
              <StyledTableRow key={entity.entity_id}>
                <StyledTableCell>
                  {entity.entity_id}
                  <Typography variant="body2" color="text.secondary">
                    {entity.attributes.name}
                  </Typography>
                </StyledTableCell>
                <StyledTableCell>{entity.state}</StyledTableCell>
                <StyledTableCell style={{ whiteSpace: "pre-wrap" }}>
                  {JSON.stringify(entity.attributes, undefined, 4)}
                </StyledTableCell>
              </StyledTableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
};

export default Entities;
