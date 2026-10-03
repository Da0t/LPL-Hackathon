"use client";

// Who is signed in to the staff workspace, so the sidebar can show them and sign them out.
import { createContext, useContext } from "react";

export type StaffUser = { displayName: string; email: string };

export const StaffContext = createContext<{ user: StaffUser; signOut: () => void } | null>(null);

export const useStaff = () => useContext(StaffContext);
