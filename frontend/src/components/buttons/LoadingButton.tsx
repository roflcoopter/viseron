import Button from "@mui/material/Button";

export type LoadingButtonProps = {
  text: string;
  icon: React.ReactNode;
  textSuccess?: string;
  iconSuccess?: React.ReactNode;
  textError?: string;
  iconError?: React.ReactNode;
  onClick: React.MouseEventHandler<HTMLButtonElement> | undefined;
  variant?: "text" | "outlined" | "contained" | undefined;
  state: "normal" | "loading" | "success" | "error";
};

export const LoadingButton = (props: LoadingButtonProps) => {
  function getColor(state: LoadingButtonProps["state"]) {
    switch (state) {
      case "normal":
        return "primary";
      case "loading":
        return "primary";
      case "success":
        return "success";
      case "error":
        return "error";
      default:
        return "primary";
    }
  }

  function getText(state: LoadingButtonProps["state"]) {
    switch (state) {
      case "normal":
        return props.text;
      case "loading":
        return props.text;
      case "success":
        return props.textSuccess ? props.textSuccess : "Success!";
      case "error":
        return props.textError ? props.textError : "Error!";
      default:
        return props.text;
    }
  }

  return (
    <Button
      color={getColor(props.state)}
      onClick={props.onClick}
      loading={props.state === "loading"}
      loadingPosition="start"
      startIcon={props.icon}
      variant={props.variant}
    >
      {getText(props.state)}
    </Button>
  );
};
