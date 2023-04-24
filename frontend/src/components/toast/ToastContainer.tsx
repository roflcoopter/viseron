import { ToastContainer as ToastifyToastContainer } from "react-toastify";

function ToastContainer() {
  return (
    <ToastifyToastContainer
      position="bottom-left"
      pauseOnFocusLoss={false}
      autoClose={5000}
      draggablePercent={50}
      theme="colored"
    />
  );
}

export default ToastContainer;
