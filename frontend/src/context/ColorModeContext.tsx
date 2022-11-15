import {
  Theme,
  ThemeOptions,
  ThemeProvider,
  createTheme,
} from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { deepmerge } from "@mui/utils";
import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

declare module "@mui/material/styles/createPalette" {
  interface ColorRange {
    50: string;
    100: string;
    200: string;
    300: string;
    400: string;
    500: string;
    600: string;
    700: string;
    800: string;
    900: string;
  }

  // eslint-disable-next-line @typescript-eslint/no-empty-interface
  interface PaletteColor extends ColorRange {}

  interface Palette {
    primaryDark: PaletteColor;
  }
}

declare module "@mui/material/styles" {
  interface Theme {
    headerHeight: number;
  }
  interface ThemeOptions {
    headerHeight?: number;
  }
}

const blue = {
  50: "#F0F7FF",
  100: "#C2E0FF",
  200: "#99CCF3",
  300: "#66B2FF",
  400: "#3399FF",
  main: "#007FFF",
  500: "#007FFF",
  600: "#0072E5",
  700: "#0059B2",
  800: "#004C99",
  900: "#003A75",
};

const grey = {
  50: "#F3F6F9",
  100: "#E7EBF0",
  200: "#E0E3E7",
  300: "#CDD2D7",
  400: "#B2BAC2",
  500: "#A0AAB4",
  600: "#6F7E8C",
  700: "#3E5060",
  800: "#2D3843",
  900: "#1A2027",
};

export type ColorModeProviderProps = {
  children: React.ReactNode;
};

export const ColorModeContext = createContext({
  toggleColorMode: () => {},
});

export function ColorModeProvider({ children }: ColorModeProviderProps) {
  const preferredMode = useMediaQuery("(prefers-color-scheme: dark)")
    ? "dark"
    : "light";
  const [mode, setMode] = useState<"light" | "dark">("light");
  const colorMode = useMemo(
    () => ({
      toggleColorMode: () => {
        setMode((prevMode) => {
          const nextMode = prevMode === "light" ? "dark" : "light";
          localStorage.setItem("chosenMode", nextMode);
          return nextMode;
        });
      },
    }),
    []
  );

  useEffect(() => {
    const chosenMode = localStorage.getItem("chosenMode");
    switch (chosenMode) {
      case "dark":
        setMode("dark");
        break;
      case "light":
        setMode("light");
        break;
      default:
        setMode(preferredMode);
    }
  }, [preferredMode]);

  const getDesignTokens = useCallback(
    (requestedMode: "light" | "dark") =>
      ({
        shape: {
          borderRadius: 5,
        },
        ...(mode === "light" && {
          text: {
            primary: grey[900],
            secondary: grey[700],
          },
        }),
        ...(mode === "dark" && {
          text: {
            primary: "#fff",
            secondary: grey[400],
          },
        }),
        grey,
        headerHeight: 56,
        palette: {
          mode,
          ...(requestedMode === "light"
            ? {
                // palette values for light mode
                divider: grey[300],
              }
            : {
                background: {
                  paper: "#0A1929",
                  default: "#0A1929",
                },
                primary: blue,
                divider: blue[900],
              }),
        },
        typography: {
          h5: {
            color: mode === "dark" ? blue[300] : blue.main,
          },
        },
      } as ThemeOptions),
    [mode]
  );

  function getThemedComponents(theme: Theme) {
    return {
      components: {
        MuiButton: {
          styleOverrides: {
            root: {
              fontWeight: 600,
              letterSpacing: 0,
            },
          },
        },
        MuiIconButton: {
          variants: [
            {
              props: { color: "primary" },
              style: {
                height: 34,
                width: 34,
                border: `1px solid ${
                  theme.palette.mode === "dark"
                    ? theme.palette.primary[900]
                    : theme.palette.grey[300]
                }`,
                borderRadius: theme.shape.borderRadius,
              },
            },
          ],
        },
        MuiDrawer: {
          styleOverrides: {
            paper: {
              backgroundColor: "primary",
              backgroundImage: "unset",
              borderRight: `1px solid ${
                theme.palette.mode === "dark"
                  ? theme.palette.primary[900]
                  : theme.palette.grey[300]
              }`,
            },
          },
        },
      },
    };
  }

  const viseronTheme = useMemo(
    () => createTheme(getDesignTokens(mode)),
    [mode, getDesignTokens]
  );
  const theme = useMemo(
    () =>
      createTheme(deepmerge(viseronTheme, getThemedComponents(viseronTheme))),
    [viseronTheme]
  );
  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </ColorModeContext.Provider>
  );
}
