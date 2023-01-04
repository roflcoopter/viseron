
import axios from 'axios';
import { QueryClient } from 'react-query';

export const BASE_URL = `${
  window.location.protocol
}${location.host}/api/v1`;

export const API_V1_URL = "/api/v1";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: async ({ queryKey: [url] }) => {
        if (typeof url === 'string') {
          const response = await axios.get(`${BASE_URL}/${url.toLowerCase()}`)
          return response.data
        }
        throw new Error('Invalid QueryKey')
      },
    },
  },
})

export type deleteRecordingParams = {
  identifier: string
  date?: string
  filename?: string
}

async function deleteRecording({identifier, date, filename}: deleteRecordingParams) {
  const url = `${API_V1_URL}/recordings/${identifier}${date ? `/${date}` : ''}${filename ? `/${filename}` : ''}`

  const response = await axios.delete(url)
  return response.data;
}

queryClient.setMutationDefaults("deleteRecording", {mutationFn: deleteRecording})

export default queryClient;
