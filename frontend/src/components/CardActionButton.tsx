import { Button, ButtonProps } from "@mui/material";
import { styled } from "@mui/material/styles";
import { Link } from "react-router-dom";

interface CardActionButtonProps {
  title: string;
  target: string;
}

type ExtendedButtonProps = ButtonProps & {
  component?: any;
  target?: any;
  to?: any;
};

const StyledButton = styled(Button)<ExtendedButtonProps>(({ theme }) => ({
  width: "50%",
  color:
    theme.palette.mode === "dark"
      ? theme.palette.primary[300]
      : theme.palette.primary.main,
  border: `1px solid ${
    theme.palette.mode === "dark"
      ? theme.palette.primary[900]
      : theme.palette.grey[300]
  }`,
}));

export function CardActionButtonLink({ title, target }: CardActionButtonProps) {
  return (
    <StyledButton
      component={Link}
      to={target}
      variant="outlined"
      size="large"
      sx={{
        width: "50%",
      }}
    >
      {title}
    </StyledButton>
  );
}

export function CardActionButtonHref({ title, target }: CardActionButtonProps) {
  return (
    <StyledButton
      component="a"
      target="_blank"
      href={target}
      variant="outlined"
      size="large"
      sx={{
        width: "50%",
      }}
    >
      {title}
    </StyledButton>
  );
}
