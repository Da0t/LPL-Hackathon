import { AccessibilityProvider } from "@/components/portal/accessibility";
import { PortalShell } from "@/components/portal/shell";
import "./portal.css";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <AccessibilityProvider><PortalShell>{children}</PortalShell></AccessibilityProvider>;
}
