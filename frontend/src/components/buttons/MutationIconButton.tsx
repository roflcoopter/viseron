import IconButton, { IconButtonProps } from "@mui/material/IconButton";
import { AxiosError } from "axios";
import * as React from "react";
import { UseMutationResult } from "react-query";

import * as types from "lib/types";

interface MutationIconButtonProps<T> extends IconButtonProps {
  mutation: UseMutationResult<
    types.APISuccessResponse,
    AxiosError<types.APIErrorResponse>,
    T
  >;
}

function MutationIconButtonInner<T>(
  props: MutationIconButtonProps<T>,
  ref: React.ForwardedRef<any>
) {
  const { mutation, ...forwardedProps } = props;
  forwardedProps.sx = {
    ...props.sx,
    transition: "color .5s ease",
    WebkitTransition: "color .5s ease",
    MozTransition: "color .5s ease",
  };

  const [color, setColor] = React.useState<"default" | "error">("default");

  React.useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    if (props.mutation.isError) {
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
  }, [props.mutation.isError]);

  return (
    <div>
      <IconButton
        {...forwardedProps}
        ref={ref}
        color={color}
        disabled={props.mutation.isLoading || props.disabled}
      />
    </div>
  );
}

const MutationIconButton = React.forwardRef(MutationIconButtonInner) as <T>(
  p: MutationIconButtonProps<T> & { ref?: React.Ref<HTMLDivElement> }
) => React.ReactElement;

export default MutationIconButton;
