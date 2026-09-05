import { createContext, useContext } from "react";
import type { Practice } from "./practice";

export const PracticeContext = createContext<Practice | null>(null);
export function useRoom() {
  const room = useContext(PracticeContext);
  if (!room) throw new Error("Practice context is required");
  return room;
}
