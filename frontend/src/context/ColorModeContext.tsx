import darkScrollbar from "@mui/material/darkScrollbar";
import {
  Theme,
  ThemeOptions,
  ThemeProvider,
  createTheme,
} from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import { deepmerge } from "@mui/utils";
import { createContext, useCallback, useMemo, useState } from "react";

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

  interface PaletteColor extends ColorRange {}

  interface Palette {
    primaryDark: PaletteColor;
    motion: string;
    recording: string;
  }
}

declare module "@mui/material/styles" {
  interface Theme {
    headerHeight: number;
    headerMargin: string;
  }
  interface ThemeOptions {
    headerHeight?: number;
    headerMargin?: string;
  }
}

declare module "@mui/material/Typography" {
  interface TypographyPropsVariantOverrides {
    uppercase: true;
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

  // Persisted user choice (or null if not set)
  const [chosenMode, setChosenMode] = useState<"light" | "dark" | null>(() => {
    const stored = localStorage.getItem("chosenMode");
    return stored === "dark" ? "dark" : stored === "light" ? "light" : null;
  });

  // Effective mode: user choice overrides system preference
  const mode = chosenMode ?? preferredMode;

  const colorMode = useMemo(
    () => ({
      toggleColorMode: () => {
        const nextMode = mode === "light" ? "dark" : "light";
        setChosenMode(nextMode);
        localStorage.setItem("chosenMode", nextMode);
      },
    }),
    [mode],
  );

  const getDesignTokens = useCallback(
    (requestedMode: "light" | "dark") =>
      ({
        shape: {
          borderRadius: 5,
        },

        ...(requestedMode === "light" && {
          text: {
            primary: grey[900],
            secondary: grey[700],
          },
        }),

        ...(requestedMode === "dark" && {
          text: {
            primary: "#fff",
            secondary: grey[400],
          },
        }),

        grey,
        headerHeight: 56,
        headerMargin: "0.5dvh",

        palette: {
          mode: requestedMode,
          motion: "#f9b4f6",
          recording: "#5df15d",
          ...(requestedMode === "light"
            ? {
                // palette values for light mode
                background: {
                  paper: "#f7f7f7",
                  default: "#ebebeb",
                },
                primary: blue,
                divider: blue[200],
              }
            : {
                // palette values for dark mode
                background: {
                  paper: "#0c1e30",
                  default: "#0A1929",
                },
                primary: blue,
                divider: blue[900],
              }),
        },

        typography: {
          fontFamily:
            '"IBM Plex Sans Variable", "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
          h5: {
            color: requestedMode === "dark" ? blue[300] : blue.main,
          },
          h6: {
            color: requestedMode === "dark" ? blue[300] : blue.main,
          },
          uppercase: {
            textTransform: "uppercase",
            letterSpacing: "0.0333333333em",
            fontWeight: 800,
          },
        },
      }) as ThemeOptions,
    [],
  );

  function getThemedComponents(theme: Theme) {
    return {
      components: {
        MuiCssBaseline: {
          styleOverrides: (themeParam: Theme) =>
            themeParam.palette.mode === "dark"
              ? darkScrollbar({
                  track: "#0f2740",
                  thumb: "#1f5286",
                  active: "#2867a9",
                })
              : darkScrollbar({
                  track: "#f1f1f1",
                  thumb: "#c1c1c1",
                  active: "#a8a8a8",
                }),
        },
        MuiContainer: {
          styleOverrides: {
            root: {
              paddingLeft: 5,
              paddingRight: 5,
            },
          },
          defaultProps: {
            maxWidth: false,
            disableGutters: true,
          },
        },
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
                    : theme.palette.primary[200]
                }`,
                borderRadius: 5, // = theme.shape.borderRadius * 5
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
                  : theme.palette.primary[200]
              }`,
            },
          },
        },
        MuiPaper: {
          styleOverrides: {
            root: {
              border: `2px solid ${
                theme.palette.mode === "dark"
                  ? theme.palette.primary[900]
                  : theme.palette.primary[200]
              }`,
              boxShadow:
                theme.palette.mode === "dark"
                  ? "0px 4px 16px rgba(0, 0, 0, 0.32), 0px 2px 4px rgba(0, 0, 0, 0.24)"
                  : "0px 2px 8px rgba(0, 0, 0, 0.08), 0px 1px 2px rgba(0, 0, 0, 0.04)",
            },
          },
        },
        MuiDialog: {
          styleOverrides: {
            paper: {
              backgroundImage: "unset",
            },
          },
        },
        MuiPickersPopper: {
          styleOverrides: {
            paper: {
              backgroundImage: "unset",
            },
          },
        },
        MuiPopover: {
          styleOverrides: {
            paper: {
              backgroundImage:
                "linear-gradient(rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.05))",
            },
          },
        },
        MuiTooltip: {
          styleOverrides: {
            tooltip: {
              backgroundColor: theme.palette.background.paper,
              border: `2px solid ${
                theme.palette.mode === "dark"
                  ? theme.palette.primary[900]
                  : theme.palette.primary[200]
              }`,
              color: theme.palette.text.primary,
              boxShadow:
                theme.palette.mode === "dark"
                  ? "0px 4px 16px rgba(0, 0, 0, 0.32), 0px 2px 4px rgba(0, 0, 0, 0.24)"
                  : "0px 2px 8px rgba(0, 0, 0, 0.08), 0px 1px 2px rgba(0, 0, 0, 0.04)",
            },
          },
        },
      },
    };
  }

  const viseronTheme = useMemo(
    () => createTheme(getDesignTokens(mode)),
    [mode, getDesignTokens],
  );
  const theme = useMemo(
    () =>
      createTheme(deepmerge(viseronTheme, getThemedComponents(viseronTheme))),
    [viseronTheme],
  );
  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </ColorModeContext.Provider>
  );
}
