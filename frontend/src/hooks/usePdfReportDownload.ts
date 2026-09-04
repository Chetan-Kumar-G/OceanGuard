import { useState } from "react";
import { ApiError, downloadVesselReportPdf } from "../api/client";

/** Shared "download the vessel report PDF" state, used by both the dashboard
 * header button and the Evidence panel's button so they don't duplicate logic. */
export function usePdfReportDownload(eventId: string | null) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    if (!eventId) return;
    setDownloading(true);
    setError(null);
    try {
      await downloadVesselReportPdf(eventId);
    } catch (err) {
      setError(err instanceof ApiError ? `Could not generate the report (HTTP ${err.status}).` : "Could not reach the server.");
    } finally {
      setDownloading(false);
    }
  }

  return { downloading, error, download };
}
