import type { Metadata } from "next";

import { DisplayBoard } from "./DisplayBoard";

export const metadata: Metadata = {
  title: "Waiting room display",
};

export default function DisplayPage() {
  return <DisplayBoard />;
}
