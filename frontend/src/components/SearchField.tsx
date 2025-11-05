import { Search } from "@carbon/icons-react";
import InputAdornment from "@mui/material/InputAdornment";
import TextField from "@mui/material/TextField";

interface SearchFieldProps {
  text: string;
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

export default function SearchField({ text, onChange }: SearchFieldProps) {
  return (
    <TextField
      label={text}
      variant="standard"
      fullWidth
      onChange={onChange}
      InputProps={{
        startAdornment: (
          <InputAdornment position="start" sx={{ paddingLeft: "5px" }}>
            <Search />
          </InputAdornment>
        ),
      }}
      InputLabelProps={{
        style: {
          paddingLeft: "16px",
        },
      }}
    />
  );
}
