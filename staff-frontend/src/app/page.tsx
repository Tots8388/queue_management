import { redirect } from "next/navigation";

/**
 * The staff app has no landing page of its own.
 *
 * It is reached from a staff terminal's bookmark, and the only way in is the
 * sign-in screen — so the root goes straight there rather than offering a
 * choice of one. Patients have their own app on its own port; nothing here
 * links back to it.
 */
export default function StaffRoot() {
  redirect("/login");
}
