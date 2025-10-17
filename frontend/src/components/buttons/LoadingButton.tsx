import Button from "@mui/material/Button";

export type LoadingButtonProps = {
  text: string;
  icon: React.ReactNode;
  textSuccess?: string;
  textError?: string;
  onClick: React.MouseEventHandler<HTMLButtonElement> | undefined;
  variant?: "text" | "outlined" | "contained" | undefined;
  state: "normal" | "loading" | "success" | "error";
};

export function LoadingButton(props: LoadingButtonProps) {
  const { text, textSuccess, textError, state, onClick, variant, icon } = props;

  function getColor(buttonState: LoadingButtonProps["state"]) {
    switch (buttonState) {
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

  function getText(buttonState: LoadingButtonProps["state"]) {
    switch (buttonState) {
      case "normal":
        return text;
      case "loading":
        return text;
      case "success":
        return textSuccess || "Success!";
      case "error":
        return textError || "Error!";
      default:
        return text;
    }
  }

  return (
    <Button
      color={getColor(state)}
      onClick={onClick}
      loading={state === "loading"}
      loadingPosition="start"
      startIcon={icon}
      variant={variant}
    >
      {getText(state)}
    </Button>
  );
}
