import IconButton, { IconButtonProps } from "@mui/material/IconButton";
import { UseMutationResult } from "@tanstack/react-query";
import * as React from "react";

import * as types from "lib/types";

interface MutationIconButtonProps<T> extends IconButtonProps {
  mutation: UseMutationResult<
    types.APISuccessResponse,
    types.APIErrorResponse,
    T
  >;
}

function MutationIconButtonInner<T>(
  props: MutationIconButtonProps<T>,
  ref: React.ForwardedRef<any>,
) {
  const { mutation, sx, disabled, ...forwardedProps } = props;

  const newProps = {
    ...forwardedProps,
    sx: {
      ...sx,
      transition: "color .5s ease",
      WebkitTransition: "color .5s ease",
      MozTransition: "color .5s ease",
    },
  };

  const [color, setColor] = React.useState<"default" | "error">("default");

  React.useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    if (mutation.isError) {
      setColor("error");
      timer = setTimeout(() => {
        setColor("default");
      }, 5000);
    }
    return () => {
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [mutation.isError]);

  return (
    <div>
      <IconButton
        // eslint-disable-next-line react/jsx-props-no-spreading
        {...newProps}
        ref={ref}
        color={color}
        disabled={mutation.isPending || disabled}
      />
    </div>
  );
}

const MutationIconButton = React.forwardRef(MutationIconButtonInner) as <T>(
  p: MutationIconButtonProps<T> & { ref?: React.Ref<HTMLDivElement> },
) => React.ReactElement<any>;

export default MutationIconButton;
