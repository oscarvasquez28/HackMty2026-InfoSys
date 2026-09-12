import { InvestigateSessionProvider } from "@/components/investigate/InvestigateSessionProvider";

export default function InvestigateLayout({ children }: { children: React.ReactNode }) {
  return <InvestigateSessionProvider>{children}</InvestigateSessionProvider>;
}
