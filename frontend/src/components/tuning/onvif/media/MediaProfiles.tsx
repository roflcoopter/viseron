import { useGetMediaProfiles } from "lib/api/actions/onvif/media";

interface MediaProfilesProps {
  cameraIdentifier: string;
}

export function MediaProfiles({ cameraIdentifier }: MediaProfilesProps) {
  useGetMediaProfiles(cameraIdentifier);
  return null;
}
