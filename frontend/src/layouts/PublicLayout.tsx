import { Suspense } from "react";
import { Outlet } from "react-router-dom";

import { Loading } from "components/loading/Loading";

function PublicLayout() {
  return (
    <Suspense fallback={<Loading text="Loading" />}>
      <Outlet />
    </Suspense>
  );
}

export default PublicLayout;
