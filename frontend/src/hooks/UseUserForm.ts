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

  // Validate password length
  if (action.type === "password") {
    if (action.value && action.value.length < 6) {
      error = "Password must be at least 6 characters.";
    }
  }

  // Validate confirm password
  if (action.type === "confirmPassword") {
    if (state.password.value !== action.value) {
      error = "Passwords do not match.";
    }
  }

  // Check if field is required
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
    // Check all fields are filled
    inputState.displayName?.value &&
    inputState.username.value &&
    inputState.password.value &&
    inputState.confirmPassword.value &&
    // Check no errors
    !inputState.displayName?.error &&
    !inputState.username.error &&
    !inputState.password.error &&
    !inputState.confirmPassword.error &&
    // Check passwords match
    inputState.password.value === inputState.confirmPassword.value &&
    // Check password length
    inputState.password.value.length >= 6 &&
    // Check role if included
    (!includeRole || (inputState.role?.value && !inputState.role?.error));

  return { inputState, dispatch, isFormValid };
};
