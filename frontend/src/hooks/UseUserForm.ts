import { useReducer } from "react";

import { TextFieldItemState } from "components/TextFieldItem";

export type InputState = {
  displayName: TextFieldItemState;
  username: TextFieldItemState;
  password: TextFieldItemState;
  confirmPassword: TextFieldItemState;
  role: TextFieldItemState;
};

type InputAction = {
  type: keyof InputState;
  value: string;
};

const initialState: InputState = {
  displayName: { label: "Display Name", value: "", error: null },
  username: { label: "Username", value: "", error: null },
  password: { label: "Password", value: "", error: null },
  confirmPassword: { label: "Confirm Password", value: "", error: null },
  role: { label: "Role", value: "read", error: null },
};

function reducer(state: InputState, action: InputAction): InputState {
  let error = null;
  if (action.type === "confirmPassword") {
    if (state.password.value !== action.value) {
      error = "Passwords do not match.";
    }
  }

  if (!action.value) {
    error = "Required.";
  }

  return {
    ...state,
    [action.type]: { value: action.value, error },
  };
}

export const useUserForm = (includeRole = false) => {
  const [inputState, dispatch] = useReducer(reducer, {
    ...initialState,
    ...(includeRole ? {} : { role: undefined }),
  });

  const isFormValid = () =>
    !inputState.displayName?.error &&
    !inputState.username.error &&
    !inputState.password.error &&
    !inputState.confirmPassword.error &&
    inputState.password.value === inputState.confirmPassword.value &&
    (!includeRole || !inputState.role?.error);

  return { inputState, dispatch, isFormValid };
};
