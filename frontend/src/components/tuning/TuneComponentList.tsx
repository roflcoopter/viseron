import { ChevronDown } from "@carbon/icons-react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Badge,
  Box,
  Card,
  CardContent,
  Tab,
  Tabs,
  Typography,
  useTheme,
} from "@mui/material";

interface TuneComponentListProps {
  selectedTab: number;
  expandedComponent: string | false;
  domainTabs: Array<{ label: string; value: string }>;
  currentDomainData: any;
  currentDomainName: string;
  onTabChange: (_event: React.SyntheticEvent, newValue: number) => void;
  onComponentChange: (
    domainName: string,
    componentName: string,
    componentData: any,
  ) => void;
}

export function TuneComponentList({
  selectedTab,
  expandedComponent,
  domainTabs,
  currentDomainData,
  currentDomainName,
  onTabChange,
  onComponentChange,
}: TuneComponentListProps) {
  const theme = useTheme();

  const renderComponentAccordion = (
    domainName: string,
    componentName: string,
    componentData: any,
  ) => {
    const componentKey = `${domainName}-${componentName}`;

    // Remove available_labels from display
    const { available_labels, ...displayData } = componentData;

    return (
      <Accordion
        key={componentKey}
        expanded={expandedComponent === componentKey}
        onChange={() =>
          onComponentChange(domainName, componentName, componentData)
        }
        sx={{ mb: 1 }}
      >
        <AccordionSummary expandIcon={<ChevronDown />}>
          <Box
            display="flex"
            justifyContent="space-between"
            alignItems="center"
            width="100%"
            mr={2}
          >
            <Typography variant="body2">{componentName}</Typography>
            {expandedComponent === componentKey && (
              <Badge badgeContent="Selected" color="primary" sx={{ mr: 3 }} />
            )}
          </Box>
        </AccordionSummary>
        <AccordionDetails style={{ paddingTop: 0 }}>
          <pre
            style={{
              margin: 0,
              padding: theme.spacing(1),
              backgroundColor: theme.palette.background.default,
              borderRadius: theme.shape.borderRadius,
              fontSize: "0.75rem",
              overflow: "auto",
              maxHeight: "50vh",
            }}
          >
            {JSON.stringify(displayData, null, 2)}
          </pre>
        </AccordionDetails>
      </Accordion>
    );
  };

  return (
    <Card
      variant="outlined"
      sx={{
        height: { md: "72.5vh" },
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <Box sx={{ borderBottom: 1, borderColor: "divider", flexShrink: 0 }}>
        <Tabs
          value={selectedTab}
          onChange={onTabChange}
          variant="scrollable"
          scrollButtons="auto"
        >
          {domainTabs.map((tab, index) => (
            <Tab
              key={tab.value}
              label={tab.label}
              sx={{ textTransform: "capitalize" }}
              value={index}
            />
          ))}
        </Tabs>
      </Box>
      <CardContent sx={{ flexGrow: 1, overflow: "auto", p: 2 }}>
        {currentDomainData && (
          <Box>
            {typeof currentDomainData === "boolean" ? (
              <Typography>
                Enabled: {currentDomainData ? "Yes" : "No"}
              </Typography>
            ) : (
              currentDomainData &&
              typeof currentDomainData === "object" &&
              Object.entries(currentDomainData as object).map(
                ([componentName, componentData]) =>
                  renderComponentAccordion(
                    currentDomainName,
                    componentName,
                    componentData,
                  ),
              )
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
