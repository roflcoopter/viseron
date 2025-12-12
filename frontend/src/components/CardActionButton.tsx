import Button, { ButtonProps } from "@mui/material/Button";
import { styled } from "@mui/material/styles";
import { Link } from "react-router-dom";

type ExtendedButtonProps = ButtonProps & {
  component?: any;
  target?: any;
  to?: any;
};

const StyledButton = styled(Button)<ExtendedButtonProps>(({ theme }) => ({
  width: "50%",
  color: theme.palette.primary.main,
  border: `1px solid ${theme.palette.grey[300]}`,
  ...theme.applyStyles("dark", {
    color: theme.palette.primary[300],
    border: `1px solid ${theme.palette.primary[900]}`,
  }),
}));

interface CardActionButtonLinkProps {
  title: string;
  target: string;
  width?: string;
  disabled?: boolean;
  startIcon?: React.ReactNode;
}

export function CardActionButtonLink({
  title,
  target,
  width = "50%",
  disabled = false,
  startIcon,
}: CardActionButtonLinkProps) {
  return (
    <StyledButton
      component={Link}
      to={target}
      variant="outlined"
      size="large"
      disabled={disabled}
      startIcon={startIcon}
      sx={{
        width,
      }}
    >
      {title}
    </StyledButton>
  );
}

interface CardActionButtonHrefProps {
  title: string;
  target: string;
}

export function CardActionButtonHref({
  title,
  target,
}: CardActionButtonHrefProps) {
  return (
    <StyledButton
      component={"a" as React.ElementType}
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
