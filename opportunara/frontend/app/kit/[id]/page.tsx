import type { Metadata } from "next";

import { KitView } from "./kit-view";

export const metadata: Metadata = {
  title: "Application kit — Scoutly",
};

export default async function KitPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const listingId = Number.parseInt(id, 10);

  return <KitView listingId={Number.isFinite(listingId) ? listingId : null} />;
}
