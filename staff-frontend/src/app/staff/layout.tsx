import { AuthProvider } from "@/lib/auth";

import { StaffShell } from "./StaffShell";

export default function StaffLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <StaffShell>{children}</StaffShell>
    </AuthProvider>
  );
}
