import { Help, Information } from "@carbon/icons-react";
import {
  Box,
  MenuItem,
  Select,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";

export interface MiscellaneousField {
  key: string;
  label: string;
  description?: string;
  type: "string" | "integer" | "float" | "boolean" | "enum";
  value: any;
  default?: any;
  lowest?: number;
  highest?: number;
  options?: string[];
}

interface MiscellaneousSectionProps {
  fields: MiscellaneousField[];
  isDrawingMode: boolean;
  isSaving: boolean;
  onFieldChange: (key: string, value: any) => void;
}

export function MiscellaneousSection({
  fields,
  isDrawingMode,
  isSaving,
  onFieldChange,
}: MiscellaneousSectionProps) {
  if (fields.length === 0) return null;

  const renderFieldWrapper = (
    field: MiscellaneousField,
    control: React.ReactNode,
  ) => (
    <Box
      key={field.key}
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        border: 1,
        borderColor: "divider",
        borderRadius: 1,
        p: 1,
        mb: 1,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
        {field.description && (
          <Tooltip title={field.description} arrow placement="top">
            <Information size={16} />
          </Tooltip>
        )}
        <Typography variant="body2" sx={{ fontWeight: 500 }}>
          {field.label}
        </Typography>
      </Box>
      {control}
    </Box>
  );

  const renderField = (field: MiscellaneousField) => {
    switch (field.type) {
      case "boolean":
        return renderFieldWrapper(
          field,
          <Switch
            checked={field.value || false}
            onChange={(e) => onFieldChange(field.key, e.target.checked)}
            disabled={isDrawingMode || isSaving}
            size="medium"
          />,
        );

      case "integer":
      case "float":
        return renderFieldWrapper(
          field,
          <TextField
            type="number"
            value={field.value ?? ""}
            onChange={(e) => {
              const val = e.target.value;
              if (val === "") {
                onFieldChange(field.key, null);
              } else {
                const parsedValue =
                  field.type === "integer"
                    ? parseInt(val, 10)
                    : parseFloat(val);
                onFieldChange(field.key, parsedValue);
              }
            }}
            disabled={isDrawingMode || isSaving}
            size="small"
            sx={{ width: "90px" }}
            inputProps={{
              step: field.type === "integer" ? 1 : 0.1,
              min: field.lowest,
              max: field.highest,
            }}
          />,
        );

      case "enum":
        return renderFieldWrapper(
          field,
          <Select
            value={field.value ?? field.default ?? ""}
            onChange={(e) => onFieldChange(field.key, e.target.value)}
            disabled={isDrawingMode || isSaving}
            size="small"
            sx={{ width: "120px" }}
          >
            {field.options?.map((option) => (
              <MenuItem key={option} value={option}>
                {option}
              </MenuItem>
            ))}
          </Select>,
        );

      case "string":
      default:
        return renderFieldWrapper(
          field,
          <TextField
            type="text"
            value={field.value ?? ""}
            onChange={(e) => onFieldChange(field.key, e.target.value)}
            disabled={isDrawingMode || isSaving}
            size="small"
            sx={{ width: "120px" }}
          />,
        );
    }
  };

  return (
    <Box mt={0.5}>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={1}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="subtitle2">Configurations</Typography>
          <Tooltip
            title="The Viseron configuration for this component based on the camera you choose. This configuration change has no effect unless you restart Viseron."
            arrow
            placement="top"
          >
            <Help size={16} />
          </Tooltip>
        </Box>
      </Box>

      <Box>{fields.map((field) => renderField(field))}</Box>
    </Box>
  );
}
