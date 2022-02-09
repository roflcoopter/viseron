import { Button } from "@mui/material";
import { Link } from "react-router-dom";

interface CardActionButtonProps {
  title: string;
  target: string;
}

export function CardActionButtonLink({ title, target }: CardActionButtonProps) {
  return (
    <Button
      component={Link}
      to={target}
      variant="outlined"
      size="large"
      sx={{
        width: "50%",
      }}
    >
      {title}
    </Button>
  );
}

export function CardActionButtonHref({ title, target }: CardActionButtonProps) {
  return (
    <Button
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
    </Button>
  );
}
