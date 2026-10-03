import { PortalShell } from "@/components/portal/shell";
import "./portal.css";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <PortalShell>{children}</PortalShell>;
}
