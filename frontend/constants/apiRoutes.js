const LOCAL_URL = "http://127.0.0.1:8000/api/";
const PRODUCTION_URL = "https://truck-routing-api-6vjl.onrender.com/api/";

function getBaseUrl() {
  const override = (import.meta.env.VITE_API_URL || "").trim();
  if (override) return override.endsWith("/") ? override : `${override}/`;
  return import.meta.env.PROD ? PRODUCTION_URL : LOCAL_URL;
}

const apiRoutes = {
  BASE_URL: getBaseUrl(),
  GEOCODE: "geocode/",
  PLAN: "plan/",
  HEATMAP: "heatmap/",
};

export default apiRoutes;
