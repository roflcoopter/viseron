import axios from "axios";
import { QueryClient } from "react-query";

export const API_V1_URL = "/api/v1";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30000,
      queryFn: async ({ queryKey: [url] }) => {
        if (typeof url === "string") {
          const response = await axios.get(`${API_V1_URL}${url.toLowerCase()}`);
          return response.data;
        }
        throw new Error("Invalid QueryKey");
      },
    },
  },
});

export type deleteRecordingParams = {
  identifier: string;
  date?: string;
  filename?: string;
};

async function deleteRecording({
  identifier,
  date,
  filename,
}: deleteRecordingParams) {
  const url = `${API_V1_URL}/recordings/${identifier}${date ? `/${date}` : ""}${
    filename ? `/${filename}` : ""
  }`;

  const response = await axios.delete(url);
  return response.data;
}

queryClient.setMutationDefaults("deleteRecording", {
  mutationFn: deleteRecording,
  onSuccess: async (_data, variables, _context) => {
    queryClient.invalidateQueries({
      predicate: (query) =>
        (query.queryKey[0] as string).startsWith(
          `/recordings/${variables.identifier}`
        ),
    });
    await queryClient.invalidateQueries([
      `/recordings/${variables.identifier}`,
    ]);
  },
});

export default queryClient;
