import { renderWithContext } from "tests/utils/renderWithContext";

import { Loading } from "components/loading/Loading";

describe("Loading Component", () => {
  test("renders with the provided text", () => {
    const { getByText } = renderWithContext(<Loading text="Loading data..." />);
    expect(getByText("Loading data...")).toBeDefined();
  });

  test("renders the Viseron logo when fullScreen is true", () => {
    const { getByRole } = renderWithContext(
      <Loading text="Loading data..." fullScreen />
    );
    expect(getByRole("img")).toBeDefined();
  });

  test("does not render the Viseron logo when fullScreen is false", () => {
    const { queryByRole } = renderWithContext(
      <Loading text="Loading data..." fullScreen={false} />
    );
    expect(queryByRole("img")).toBeNull();
  });

  test("renders the circular progress indicator", () => {
    const { getByRole } = renderWithContext(<Loading text="Loading data..." />);
    expect(getByRole("progressbar")).toBeDefined();
  });
});
