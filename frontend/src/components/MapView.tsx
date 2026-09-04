import { useEffect, useRef } from "react";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type {
  CandidateVessel,
  ForecastRun,
  GeoJSONPolygon,
  RankingResult,
  SourceHypothesisWindow,
  TemporalSpillState,
} from "../api/types";
import { boundsOf, circlePolygon, flattenCoords } from "../lib/geo";
import type { LayerVisibility } from "./LayerToggles";

const SPILL_LAYER_IDS = ["spill-fill", "spill-outline"];
const SOURCE_LAYER_IDS = ["hypothesis-circle-fill", "hypothesis-circle-outline", "hypothesis-point"];
const VESSEL_LAYER_IDS = ["vessels-point"];
const FORECAST_LAYER_IDS = [
  "forecast-envelope-fill",
  "forecast-envelope-outline",
  "forecast-predicted-fill",
  "forecast-predicted-outline",
];

const SOURCES = {
  spill: "spill-polygons",
  hypothesisCircle: "hypothesis-circle",
  hypothesisPoint: "hypothesis-point",
  forecastEnvelope: "forecast-envelope",
  forecastPredicted: "forecast-predicted",
  vessels: "vessels",
} as const;

const EMPTY_FC = { type: "FeatureCollection" as const, features: [] as GeoJSON.Feature[] };

const STATE_COLOR: Record<string, string> = {
  OBSERVED: "#ff7a45",
  INTERPOLATED: "#ffb066",
  PREDICTED: "#8a8f98",
};

interface MapViewProps {
  center: [number, number]; // [lon, lat]
  states: TemporalSpillState[];
  hypotheses: SourceHypothesisWindow[];
  candidates: CandidateVessel[];
  ranking: RankingResult | null;
  forecastRun: ForecastRun | null;
  selectedMmsi: string | null;
  onSelectVessel: (mmsi: string | null) => void;
  layers: LayerVisibility;
}

export default function MapView({
  center,
  states,
  hypotheses,
  candidates,
  ranking,
  forecastRun,
  selectedMmsi,
  onSelectVessel,
  layers,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const loadedRef = useRef(false);
  const firstFitDoneRef = useRef<string | null>(null);

  // ---- map init (once) ------------------------------------------------
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          "osm-tiles": {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm-tiles-layer", type: "raster", source: "osm-tiles" }],
        glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      },
      center,
      zoom: 6,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", () => {
      map.addSource(SOURCES.spill, { type: "geojson", data: EMPTY_FC });
      map.addLayer({
        id: "spill-fill",
        type: "fill",
        source: SOURCES.spill,
        paint: { "fill-color": ["get", "color"], "fill-opacity": ["get", "opacity"] },
      });
      map.addLayer({
        id: "spill-outline",
        type: "line",
        source: SOURCES.spill,
        paint: { "line-color": ["get", "color"], "line-width": 1.5 },
      });

      map.addSource(SOURCES.forecastEnvelope, { type: "geojson", data: EMPTY_FC });
      map.addLayer({
        id: "forecast-envelope-fill",
        type: "fill",
        source: SOURCES.forecastEnvelope,
        paint: { "fill-color": "#4f8dff", "fill-opacity": 0.08 },
      });
      map.addLayer({
        id: "forecast-envelope-outline",
        type: "line",
        source: SOURCES.forecastEnvelope,
        paint: { "line-color": "#4f8dff", "line-width": 1, "line-dasharray": [2, 2] },
      });

      map.addSource(SOURCES.forecastPredicted, { type: "geojson", data: EMPTY_FC });
      map.addLayer({
        id: "forecast-predicted-fill",
        type: "fill",
        source: SOURCES.forecastPredicted,
        paint: { "fill-color": "#4f8dff", "fill-opacity": 0.35 },
      });
      map.addLayer({
        id: "forecast-predicted-outline",
        type: "line",
        source: SOURCES.forecastPredicted,
        paint: { "line-color": "#a9c6ff", "line-width": 1.5 },
      });

      map.addSource(SOURCES.hypothesisCircle, { type: "geojson", data: EMPTY_FC });
      map.addLayer({
        id: "hypothesis-circle-fill",
        type: "fill",
        source: SOURCES.hypothesisCircle,
        paint: { "fill-color": "#ffd93d", "fill-opacity": 0.12 },
      });
      map.addLayer({
        id: "hypothesis-circle-outline",
        type: "line",
        source: SOURCES.hypothesisCircle,
        paint: { "line-color": "#ffd93d", "line-width": 1.5, "line-dasharray": [3, 2] },
      });

      map.addSource(SOURCES.hypothesisPoint, { type: "geojson", data: EMPTY_FC });
      map.addLayer({
        id: "hypothesis-point",
        type: "circle",
        source: SOURCES.hypothesisPoint,
        paint: {
          "circle-radius": 6,
          "circle-color": "#ffd93d",
          "circle-stroke-color": "#1a1d23",
          "circle-stroke-width": 2,
        },
      });

      map.addSource(SOURCES.vessels, { type: "geojson", data: EMPTY_FC });
      map.addLayer({
        id: "vessels-point",
        type: "circle",
        source: SOURCES.vessels,
        paint: {
          "circle-radius": ["case", ["get", "selected"], 10, ["get", "topCandidate"], 8, 6],
          "circle-color": ["get", "color"],
          "circle-stroke-color": "#0d0f13",
          "circle-stroke-width": ["case", ["get", "selected"], 3, 1.5],
        },
      });

      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 12 });
      map.on("mouseenter", "vessels-point", (e) => {
        map.getCanvas().style.cursor = "pointer";
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties as Record<string, unknown>;
        popup
          .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
          .setHTML(
            `<strong>MMSI ${p.mmsi}</strong><br/>rank #${p.rank ?? "–"} · score ${p.score ?? "–"}<br/>${Number(p.distance_km).toFixed(1)} km from source`,
          )
          .addTo(map);
      });
      map.on("mouseleave", "vessels-point", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });
      map.on("click", "vessels-point", (e) => {
        const f = e.features?.[0];
        if (f) onSelectVessel(String((f.properties as Record<string, unknown>).mmsi));
      });
      map.on("click", (e) => {
        const hits = map.queryRenderedFeatures(e.point, { layers: ["vessels-point"] });
        if (hits.length === 0) onSelectVessel(null);
      });

      loadedRef.current = true;
      forceUpdate();
    });

    // The container can change size without the window resizing - e.g. it's
    // moved into/out of a floating DockableWindow - so MapLibre needs an
    // explicit nudge or it keeps rendering at its old canvas size.
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
      loadedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // recentre when the event (and therefore the AOI) changes
  useEffect(() => {
    mapRef.current?.jumpTo({ center, zoom: 6 });
    firstFitDoneRef.current = null;
  }, [center]);

  function applyLayerVisibility() {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    const apply = (ids: string[], visible: boolean) => {
      for (const id of ids) {
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
      }
    };
    apply(SPILL_LAYER_IDS, layers.spill);
    apply(SOURCE_LAYER_IDS, layers.source);
    apply(VESSEL_LAYER_IDS, layers.vessels);
    apply(FORECAST_LAYER_IDS, layers.forecast);
  }

  function forceUpdate() {
    updateSpill();
    updateForecast();
    updateHypotheses();
    updateVessels();
    applyLayerVisibility();
  }

  function updateSpill() {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    const features: GeoJSON.Feature[] = states
      .filter((s) => s.polygon_geojson?.coordinates?.length)
      .map((s) => ({
        type: "Feature",
        geometry: s.polygon_geojson as unknown as GeoJSON.Geometry,
        properties: {
          color: STATE_COLOR[s.state_type] ?? "#ff7a45",
          opacity: s.state_type === "OBSERVED" ? 0.28 : 0.12,
          observation_id: s.observation_id,
        },
      }));
    (map.getSource(SOURCES.spill) as maplibregl.GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features,
    });

    if (firstFitDoneRef.current !== states[0]?.event_id && features.length > 0) {
      const bounds = boundsOf(features.flatMap((f) => flattenCoords(f.geometry as unknown as GeoJSONPolygon)));
      if (bounds) {
        map.fitBounds(bounds, { padding: 80, maxZoom: 10, duration: 600 });
        firstFitDoneRef.current = states[0]?.event_id ?? null;
      }
    }
  }

  function updateForecast() {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    const envelope = forecastRun
      ? [{ type: "Feature" as const, geometry: forecastRun.forecast_envelope_geojson as unknown as GeoJSON.Geometry, properties: {} }]
      : [];
    const predicted = forecastRun
      ? [{ type: "Feature" as const, geometry: forecastRun.predicted_polygon_geojson as unknown as GeoJSON.Geometry, properties: {} }]
      : [];
    (map.getSource(SOURCES.forecastEnvelope) as maplibregl.GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: envelope,
    });
    (map.getSource(SOURCES.forecastPredicted) as maplibregl.GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: predicted,
    });
  }

  function updateHypotheses() {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    const best = hypotheses.find((h) => h.ensemble_id === -1) ?? hypotheses[0];
    const circleFeatures: GeoJSON.Feature[] = best
      ? [
          {
            type: "Feature",
            geometry: circlePolygon(best.source_location.lon, best.source_location.lat, best.uncertainty_radius_km) as unknown as GeoJSON.Geometry,
            properties: {},
          },
        ]
      : [];
    const pointFeatures: GeoJSON.Feature[] = best
      ? [
          {
            type: "Feature",
            geometry: { type: "Point", coordinates: [best.source_location.lon, best.source_location.lat] },
            properties: { id: best.source_hypothesis_id },
          },
        ]
      : [];
    (map.getSource(SOURCES.hypothesisCircle) as maplibregl.GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: circleFeatures,
    });
    (map.getSource(SOURCES.hypothesisPoint) as maplibregl.GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: pointFeatures,
    });
  }

  function updateVessels() {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    const rankByMmsi = new Map(ranking?.candidates.map((c) => [c.candidate_mmsi, c]) ?? []);
    const features: GeoJSON.Feature[] = candidates
      .filter((c) => c.closest_approach_lat != null && c.closest_approach_lon != null)
      .map((c) => {
        const r = rankByMmsi.get(c.mmsi);
        const top = (r?.rank ?? 99) <= 3;
        return {
          type: "Feature",
          geometry: { type: "Point", coordinates: [c.closest_approach_lon!, c.closest_approach_lat!] },
          properties: {
            mmsi: c.mmsi,
            rank: r?.rank ?? null,
            score: r ? r.final_score.toFixed(2) : null,
            distance_km: c.distance_to_source_effective_km,
            topCandidate: top,
            selected: c.mmsi === selectedMmsi,
            color: c.mmsi === selectedMmsi ? "#ff3b3b" : top ? "#ffb347" : "#7fb2ff",
          },
        };
      });
    (map.getSource(SOURCES.vessels) as maplibregl.GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features,
    });
  }

  useEffect(updateSpill, [states]);
  useEffect(updateForecast, [forecastRun]);
  useEffect(updateHypotheses, [hypotheses]);
  useEffect(updateVessels, [candidates, ranking, selectedMmsi]);

  useEffect(applyLayerVisibility, [layers]);

  return <div ref={containerRef} className="map-container" />;
}
