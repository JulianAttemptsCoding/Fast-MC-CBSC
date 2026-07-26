import type { Metadata } from "next";
import { ZdcDashboard } from "./ZdcDashboard";

export const metadata: Metadata = {
  title: "CBSC ZDC Event Observatory",
  description:
    "Epoch-by-epoch Geant4 and Fast-MC calorimeter event comparison.",
};

export default function Home() {
  return <ZdcDashboard />;
}
